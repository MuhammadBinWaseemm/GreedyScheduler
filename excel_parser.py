import pandas as pd
import re
from typing import List, Dict, Set

class CourseData:
    def __init__(self, code, title, credit_hours, instructors, section_groups, is_lab=False, num_students=50, preferred_building=None):
        self.code = code
        self.title = title
        self.credit_hours = credit_hours
        self.instructors = instructors
        self.section_groups = section_groups  # List of strings e.g., ["FCSE", "Section A"]
        self.is_lab = is_lab
        self.num_students = num_students
        self.preferred_building = preferred_building

class RoomData:
    def __init__(self, name, building, capacity=60, is_lab=False):
        self.name = name
        self.building = building
        self.capacity = capacity
        self.is_lab = is_lab

class TimetableExcelParser:
    """
    Advanced Data Ingestion & Normalization Layer.
    Extracts, cleans, and restructures raw Excel inputs for the high-performance CSP engine.
    """
    def _parse_credit_hours(self, ch_raw):
        """
        Handles messy credit hours strings:
        "3" -> 3, False
        "2CH" -> 2, False
        "0-1" -> 1, True
        "1-3-2" -> 3, False
        """
        if pd.isna(ch_raw) or str(ch_raw).strip() == "":
            return 3, False
            
        ch_str = str(ch_raw).strip().upper()
        
        if '-' in ch_str:
            parts = [int(p) for p in re.findall(r'\d+', ch_str)]
            if len(parts) >= 2:
                if parts[0] == 0:
                    return parts[1], True
                elif len(parts) >= 3:
                    return parts[1], False
            return parts[-1] if parts else 3, True if '0-' in ch_str else False
            
        match = re.search(r'\d+', ch_str)
        if match:
            return int(match.group()), False
        
        return 3, False

    def normalize_section(self, s):
        s = s.upper().strip()
        # Look for standalone section letters at the end (e.g. 'BSCS A' -> 'A')
        match = re.search(r'\b([A-Z])\b$', s)
        if match:
            return match.group(1)
        # Fallback to single character check if string is exactly 1 letter
        if len(s) == 1 and s.isalpha():
            return s
        return s

    def parse_courses(self, filepath: str) -> List[CourseData]:
        courses = []
        try:
            sheets = pd.read_excel(filepath, sheet_name=None)
            
            total_slots = 0
            unique_teachers = set()
            unique_sections = set()
            
            for faculty, df in sheets.items():
                df.columns = df.columns.astype(str).str.lower().str.strip()
                
                col_map = {}
                for c in df.columns:
                    if 'code' in c: col_map['code'] = c
                    elif 'title' in c: col_map['title'] = c
                    elif 'credit' in c or 'ch' in c: col_map['ch'] = c
                    elif 'instructor' in c or 'teacher' in c: col_map['instructor'] = c
                    elif 'section' in c: col_map['section'] = c
                    
                if 'code' not in col_map:
                    continue
                    
                for _, row in df.iterrows():
                    raw_code = str(row[col_map['code']]).strip()
                    if raw_code.lower() in ('nan', 'none', ''):
                        continue
                        
                    code = re.sub(r'\s+', '', raw_code).upper()
                    
                    raw_ch = row.get(col_map.get('ch', ''), '')
                    ch, is_lab = self._parse_credit_hours(raw_ch)
                    
                    if code.endswith('L') or code.startswith('IF'):
                        is_lab = True
                        ch = 3
                    
                    title = str(row.get(col_map.get('title', ''), '')).strip()
                    if not title or title.lower() in ('nan', 'none'):
                        title = "Unknown Title"
                    
                    instructor = str(row.get(col_map.get('instructor', ''), '')).strip()
                    if not instructor or instructor.lower() in ('nan', 'none'):
                        # Assign a unique dummy instructor to prevent 40+ hour load bottlenecks on a single 'TBA' person
                        safe_code = code.replace('/', '_').replace(',', '_').replace('&', '_')
                        instructors = [f"TBA_{safe_code}"]
                    else:
                        instructors = [i.strip() for i in re.split(r'[,&/]', instructor) if i.strip()]
                        
                    section_raw = str(row.get(col_map.get('section', ''), '')).strip()
                    if not section_raw or section_raw.lower() in ('nan', 'none'):
                        # If no section column, assume the sheet name is the section! (per user request)
                        section_raw = faculty
                        
                    parsed_sections = [s.strip() for s in re.split(r'[+,&|]', section_raw) if s.strip()]
                    section_groups = [self.normalize_section(s) for s in parsed_sections]
                    
                    is_first_year = "semester 1" in section_raw.lower() or "1st semester" in section_raw.lower() or "first semester" in section_raw.lower()
                    base_students = 80 if is_first_year else 40
                    
                    courses.append(CourseData(
                        code=code,
                        title=title,
                        credit_hours=ch,
                        instructors=instructors,
                        section_groups=section_groups,
                        is_lab=is_lab,
                        num_students=base_students,
                        preferred_building=faculty  # Faculty name maps dynamically to building
                    ))
                    
            # ==========================================
            # DYNAMIC COURSE MERGING (CO-LOCATED SECTIONS)
            # ==========================================
            merged_dict = {}
            unmerged_courses = []
            
            for c in courses:
                can_merge = False
                if c.is_lab:
                    match = re.search(r'\d', c.code)
                    if match and match.group() == '1':
                        can_merge = True
                else:
                    can_merge = True
                    
                if not can_merge:
                    unmerged_courses.append(c)
                else:
                    inst_tuple = tuple(sorted(c.instructors))
                    # Group by code, CH, exact same instructors, and faculty
                    key = (c.code, c.credit_hours, inst_tuple, c.preferred_building)
                    
                    if key not in merged_dict:
                        merged_dict[key] = [c]
                    else:
                        merged = False
                        for existing in merged_dict[key]:
                            # STRICT RULE: Maximum merge of TWO sections for same lecturer
                            if len(existing.section_groups) + len(c.section_groups) <= 2:
                                original_sections = list(existing.section_groups)
                                for s in c.section_groups:
                                    if s not in existing.section_groups:
                                        existing.section_groups.append(s)
                                existing.num_students += c.num_students
                                merged = True
                                print(f"[MERGE] {c.code} ({', '.join(c.instructors)}): Combined {original_sections} with {c.section_groups} -> {existing.section_groups}")
                                break
                        if not merged:
                            merged_dict[key].append(c)
                            
            final_courses = unmerged_courses
            for v_list in merged_dict.values():
                final_courses.extend(v_list)
            
            # Recalculate accurate metadata after merging
            total_slots = sum(c.credit_hours for c in final_courses)
            unique_teachers = set()
            unique_sections = set()
            for c in final_courses:
                unique_teachers.update(c.instructors)
                unique_sections.update(c.section_groups)
            
            print("====================================")
            print("      DATA INGESTION SUMMARY        ")
            print("====================================")
            print(f"Total Courses Loaded : {len(final_courses)} (Merged duplicates)")
            print(f"Total Unique Teachers: {len(unique_teachers)}")
            print(f"Total Unique Sections: {len(unique_sections)}")
            print(f"Total Slot Demand    : {total_slots}")
            print("====================================")
            
            return final_courses
            
        except Exception as e:
            print(f"[Error] Failed to parse courses file: {e}")
            return []

    def parse_rooms(self, filepath: str) -> List[RoomData]:
        rooms = []
        try:
            sheets = pd.read_excel(filepath, sheet_name=None)
            
            for sheet_name, df in sheets.items():
                df.columns = df.columns.astype(str).str.lower().str.strip()
                col_map = {}
                for c in df.columns:
                    if 'room' in c: col_map['room'] = c
                    elif 'building' in c: col_map['building'] = c
                    elif 'capacity' in c: col_map['capacity'] = c
                    elif 'type' in c: col_map['type'] = c
                    
                if 'room' not in col_map:
                    continue
                    
                df = df.dropna(subset=[col_map['room']])
                
                for _, row in df.iterrows():
                    name = str(row[col_map['room']]).strip()
                    if name.lower() in ('nan', 'none', ''):
                        continue
                        
                    building = str(row.get(col_map.get('building', ''), sheet_name)).strip()
                    if building.lower() in ('nan', 'none', ''):
                        building = sheet_name
                    
                    cap_raw = str(row.get(col_map.get('capacity', ''), '60'))
                    try:
                        cap_match = re.search(r'\d+', cap_raw)
                        capacity = int(cap_match.group()) if cap_match else 60
                    except Exception:
                        capacity = 60
                    
                    # Prefer explicit Type column, fallback to name-based detection
                    if 'type' in col_map:
                        type_val = str(row.get(col_map['type'], '')).strip().lower()
                        is_lab = (type_val == 'lab')
                    else:
                        is_lab = 'lab' in name.lower()
                        
                    rooms.append(RoomData(
                        name=name,
                        building=building,
                        capacity=capacity,
                        is_lab=is_lab
                    ))
            return rooms
            
        except Exception as e:
            print(f"[Error] Failed to parse rooms file: {e}")
            return []

    def extract_metadata(self, courses: List[CourseData], rooms: List[RoomData]) -> Dict[str, List[str]]:
        teachers = set()
        sections = set()
        buildings = set()
        
        for c in courses:
            for inst in c.instructors:
                teachers.add(inst)
            for s in c.section_groups:
                sections.add(s)
            if isinstance(c.preferred_building, list):
                buildings.update(c.preferred_building)
            else:
                buildings.add(c.preferred_building)
            
        for r in rooms:
            buildings.add(r.building)
            
        return {
            "teachers": sorted(list(teachers)),
            "sections": sorted(list(sections)),
            "buildings": sorted(list(buildings))
        }
