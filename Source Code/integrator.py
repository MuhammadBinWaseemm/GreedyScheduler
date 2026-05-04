import json
from excel_parser import TimetableExcelParser
from scheduler_engine import TimetableScheduler, Course, Room

class TimetableIntegrator:
    def __init__(self):
        self.parser = TimetableExcelParser()

    def generate_timetable(self, courses_filepath: str, rooms_filepath: str = None, minimize_friday: bool = False, custom_rooms=None):
        # ==========================================
        # 1. LOAD EXCEL DATA
        # ==========================================
        print("-> Parsing Excel files...")
        raw_courses = self.parser.parse_courses(courses_filepath)
        
        if not raw_courses:
            print("[Error] Empty data or failed to read Excel files.")
            return None

        # ---------------------------------------------------------
        # USER OVERRIDE: Focus strictly on Section A and AcB Rooms
        # ---------------------------------------------------------
        print("ALL SECTIONS:", set(s for c in raw_courses for s in c.section_groups))
        
        import re
        filtered_courses = []
        unknown_prefixes = set()
        
        if custom_rooms:
            raw_rooms = custom_rooms
        else:
            raw_rooms = self.get_default_rooms()
            
        # Identify new, user-added buildings to make them globally unrestricted
        known_core_bldgs = {"AcB", "BB", "FCSE", "FEE", "FES", "FME", "FMCE", "IC"}
        unrestricted_bldgs = list({r.building for r in raw_rooms} - known_core_bldgs)
        
        for c in raw_courses:
            match = re.search(r'\d', c.code)
            is_valid_year = match and match.group() in ['1', '2', '3', '4']
            
            if is_valid_year:
                digit = match.group()
            #    sem = int(digit) * 2 - 1
                sem_str = f"Year {digit}"
                
                # Namespace sections by semester to distinguish 1st/2nd/3rd year cohorts
                new_sections = []
                for s in c.section_groups:
                    s_clean = s.strip()
                    if len(s_clean) == 1 or not s_clean.lower().startswith("sec"):
                        new_sections.append(f"Section {s_clean}, {sem_str}")
                    else:
                        new_sections.append(f"{s_clean}, {sem_str}")
                c.section_groups = new_sections
                
                prefix_match = re.match(r'[A-Z]+', c.code.upper())
                prefix = prefix_match.group() if prefix_match else ""
                
                if c.is_lab:
                    all_lab_bldgs = ["AcB", "FCSE", "FES", "FEE", "FMCE", "FME"]
                    if prefix in ["CS", "AI", "DS", "CY", "CX", "SE"]:
                        bldgs = ["AcB", "FCSE"] + all_lab_bldgs
                    elif prefix == "CE":
                        bldgs = ["FCSE", "AcB"] + all_lab_bldgs
                    elif prefix == "CV":
                        bldgs = ["AcB"] + all_lab_bldgs
                    elif prefix == "CH":
                        bldgs = ["AcB"] + all_lab_bldgs
                    elif prefix == "EE":
                        bldgs = ["FEE"] + all_lab_bldgs
                    elif prefix == "MM":
                        bldgs = ["FMCE"] + all_lab_bldgs
                    elif prefix == "ME":
                        bldgs = ["FME"] + all_lab_bldgs
                    elif prefix == "PH":
                        bldgs = ["FES"] + all_lab_bldgs
                    elif prefix == "ES":
                        bldgs = ["FES"] + all_lab_bldgs
                    else:
                        bldgs = all_lab_bldgs
                        
                    # Remove duplicates to maintain clean priority order
                    seen = set()
                    bldgs = [x for x in bldgs if not (x in seen or seen.add(x))]
                else:
                    if prefix in ["HM", "MS", "AF"]:
                        bldgs = ["BB"]
                    elif prefix in ["ES", "PH", "MT"]:
                        bldgs = ["FES"]
                    elif prefix in ["CS", "AI", "DS", "CY", "CE", "CX", "SE"]:
                        bldgs = ["FCSE", "AcB"]
                    elif prefix == "EE":
                        bldgs = ["FEE"]
                    elif prefix in ["MM", "CH"]:
                        bldgs = ["FMCE"]
                    elif prefix == "ME":
                        bldgs = ["FME"]
                    elif prefix == "CV":
                        bldgs = ["AcB"]
                    else:
                        bldgs = ["AcB", "FCSE", "FES", "FEE", "FMCE", "FME", "BB"]
                        unknown_prefixes.add(prefix)
                    
                # Append any unrestricted custom buildings to the allowed list
                c.preferred_building = bldgs + unrestricted_bldgs
                filtered_courses.append(c)
                
        raw_courses = filtered_courses
        
        if unknown_prefixes:
            print(f"[Warning] Found unusual course prefixes routed to AcB: {unknown_prefixes}")
            
        print(f"FILTERED COURSES: {len(filtered_courses)} (All Sections - Years 1, 2, 3, 4)")

        # ==========================================
        # 2. METADATA EXTRACTION & ID MAPPING
        # ==========================================
        print("-> Extracting metadata and ID mappings...")
        metadata = self.parser.extract_metadata(raw_courses, raw_rooms)
        
        teacher_to_id = {name: idx for idx, name in enumerate(metadata["teachers"])}
        section_to_id = {name: idx for idx, name in enumerate(metadata["sections"])}
        
        id_to_teacher = {idx: name for name, idx in teacher_to_id.items()}
        id_to_room = {idx: r.name for idx, r in enumerate(raw_rooms)}
        id_to_section = {idx: name for name, idx in section_to_id.items()}
        
        engine_rooms = [
            Room(r_id=idx, is_lab=r.is_lab, capacity=r.capacity, building=r.building) 
            for idx, r in enumerate(raw_rooms)
        ]
        
        engine_courses = []
        for idx, c in enumerate(raw_courses):
            engine_courses.append(Course(
                c_id=idx,
                code=c.code,
                credit_hours=c.credit_hours,
                instructor_ids=[teacher_to_id[inst] for inst in c.instructors],
                section_ids=[section_to_id[s] for s in c.section_groups],
                is_lab=c.is_lab,
                num_students=c.num_students,
                preferred_building=c.preferred_building
            ))

        # ==========================================
        # 3. RUN SCHEDULER
        # ==========================================
        print("-> Running High-Performance Scheduler...")
        scheduler = TimetableScheduler(
            num_teachers=len(teacher_to_id),
            num_sections=len(section_to_id),
            num_rooms=len(engine_rooms)
        )
        
        scheduler.load_data(engine_courses, engine_rooms)
        success = scheduler.solve(max_refinement_steps=25000, max_restarts=5, minimize_friday=minimize_friday)
        
        if not success:
            debug_text = "=== DEBUG START: UNRESOLVED COLLISIONS ===\n"
            for c in scheduler.unassigned_courses:
                raw = raw_courses[c.id]
                teacher_names = [id_to_teacher[tid] for tid in c.instructor_ids]
                section_names = [id_to_section[sid] for sid in c.section_ids]
                debug_text += f"Course:      {raw.code} | {raw.title}\n"
                debug_text += f"Sections:    {', '.join(section_names)}\n"
                debug_text += f"Instructors: {', '.join(teacher_names)}\n"
                debug_text += f"Is Lab:      {c.is_lab}\n"
                debug_text += f"Pref. Bldgs: {c.preferred_buildings}\n"
                debug_text += "-" * 50 + "\n"
            debug_text += "=== DEBUG END: UNRESOLVED COLLISIONS ===\n"
            print(debug_text)
            return debug_text

        # ==========================================
        # 4. PRODUCE FINAL DATA STRUCTURE
        # ==========================================
        print("-> Generating structured final output...")
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        final_output = []
        
        for c in scheduler.courses:
            if c.assigned_room_id == -1: continue
            
            raw = raw_courses[c.id]
            teacher_names = [id_to_teacher[tid] for tid in c.instructor_ids]
            room_name = id_to_room[c.assigned_room_id]
            
            slots = [i for i in range(40) if (c.assigned_slots_mask & (1 << i))]
            schedule_blocks = []
            
            slots_labels = ["8:00-8:50", "9:00-9:50", "10:30-11:20", "11:30-12:20", "12:30-1:20", "2:30-3:20", "3:30-4:20", "4:30-5:20"]
            for s in slots:
                day_name = days[s // 8]
                slot_idx = s % 8
                schedule_blocks.append({
                    "day": day_name,
                    "slot_index": slot_idx,
                    "time": slots_labels[slot_idx]
                })
                
            final_output.append({
                "course_code": raw.code,
                "course_title": raw.title,
                "instructors": teacher_names,
                "instructor": ", ".join(teacher_names),
                "sections": raw.section_groups,
                "room": room_name,
                "building": engine_rooms[c.assigned_room_id].building,
                "is_lab": raw.is_lab,
                "schedule": schedule_blocks
            })

        print("-> Pipeline Execution Complete!")
        return final_output

    def get_default_rooms(self):
        from excel_parser import RoomData
        raw_rooms = []
        # AcB
        raw_rooms.extend([RoomData(f"AcB LH{i}", "AcB", capacity=100) for i in range(1, 13)])
        raw_rooms.extend([RoomData(f"AcB Main{i}", "AcB", capacity=200) for i in range(1, 4)])
        # Brabers Building (BB)
        raw_rooms.append(RoomData("BB Main", "BB", capacity=200))
        raw_rooms.append(RoomData("BB LH2", "BB", capacity=100))
        raw_rooms.extend([RoomData(f"BB EH{i}", "BB", capacity=80) for i in range(1, 5)])
        # FCSE
        raw_rooms.extend([RoomData(f"CS LH{i}", "FCSE", capacity=100) for i in range(1, 4)])
        # FEE
        raw_rooms.extend([RoomData(f"EE LH{i}", "FEE", capacity=100) for i in range(4, 7)])
        raw_rooms.append(RoomData("EE Main", "FEE", capacity=200))
        # FES
        raw_rooms.extend([RoomData(f"ES LH{i}", "FES", capacity=100) for i in (1, 2, 4)])
        raw_rooms.append(RoomData("ES Main", "FES", capacity=200))
        # FME
        raw_rooms.extend([RoomData(f"ME LH{i}", "FME", capacity=100) for i in range(1, 4)])
        raw_rooms.append(RoomData("ME Main", "FME", capacity=200))
        # FMCE
        raw_rooms.extend([RoomData(f"MCE LH{i}", "FMCE", capacity=100) for i in range(1, 5)])
        raw_rooms.append(RoomData("MCE Main", "FMCE", capacity=200))
        # Incubation Center
        raw_rooms.extend([
            RoomData("Sem. Hall (Incubation Center)", "IC", capacity=150),
            RoomData("WR 1", "IC", capacity=60),
            RoomData("WR 2", "IC", capacity=60)
        ])

        # Labs
        raw_rooms.extend([RoomData(f"AcB CS/AI/SE Lab {i}", "AcB", capacity=120, is_lab=True) for i in range(1, 5)])
        raw_rooms.extend([RoomData(f"AcB CVE Lab {i}", "AcB", capacity=120, is_lab=True) for i in range(1, 4)])
        raw_rooms.extend([RoomData(f"AcB CH Lab {i}", "AcB", capacity=120, is_lab=True) for i in range(1, 4)])
        
        raw_rooms.extend([RoomData(f"FCSE CE Lab {i}", "FCSE", capacity=120, is_lab=True) for i in range(1, 3)])
        raw_rooms.append(RoomData("FCSE CS/AI Lab 1", "FCSE", capacity=120, is_lab=True))
        
        raw_rooms.extend([RoomData(f"FEE EE Lab {i}", "FEE", capacity=120, is_lab=True) for i in range(1, 3)])
        raw_rooms.extend([RoomData(f"FMCE MM Lab {i}", "FMCE", capacity=120, is_lab=True) for i in range(1, 4)])
        raw_rooms.extend([RoomData(f"FME ME Lab {i}", "FME", capacity=120, is_lab=True) for i in range(1, 6)])
        raw_rooms.extend([RoomData(f"FES PH Lab {i}", "FES", capacity=120, is_lab=True) for i in range(1, 3)])
        raw_rooms.extend([RoomData(f"FES ES Lab {i}", "FES", capacity=120, is_lab=True) for i in range(1, 4)])
        return raw_rooms
