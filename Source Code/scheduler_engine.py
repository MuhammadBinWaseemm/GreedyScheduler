import random
import math
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(message)s')

class Course:
    def __init__(self, c_id, code, credit_hours, instructor_ids, section_ids, is_lab, num_students, preferred_building=None):
        self.id = c_id
        self.code = code
        self.credit_hours = credit_hours
        self.instructor_ids = instructor_ids
        self.section_ids = section_ids  
        self.is_lab = is_lab
        self.num_students = num_students
        self.preferred_buildings = preferred_building if isinstance(preferred_building, list) else [preferred_building]
        self.valid_rooms = []
        self.assigned_room_id = -1
        self.assigned_slots_mask = 0
        self.conflict_count = 0

class Room:
    def __init__(self, r_id, is_lab, capacity, building):
        self.id = r_id
        self.is_lab = is_lab
        self.capacity = capacity
        self.building = building

class TimetableScheduler:
    def __init__(self, num_teachers, num_sections, num_rooms):
        self.num_teachers = num_teachers
        self.num_sections = num_sections
        self.num_rooms = num_rooms
        self.teacher_busy = [0] * num_teachers
        self.section_busy = [0] * num_sections
        self.room_busy = [0] * num_rooms
        self.teacher_grid = [[None] * 40 for _ in range(num_teachers)]
        self.section_grid = [[None] * 40 for _ in range(num_sections)]
        self.room_grid = [[None] * 40 for _ in range(num_rooms)]
        self.courses = []
        self.rooms = []
        self.unassigned_courses = []
        self._precompute_masks()

    def _precompute_masks(self):
        self.lab_masks_2 = self._generate_consecutive_masks(2)
        masks = []
        for d in range(5):
            for s in [0, 1, 5]:
                mask = 0
                for i in range(3):
                    mask |= (1 << (d * 8 + s + i))
                masks.append(mask)
        self.lab_masks_3 = masks

    def _generate_consecutive_masks(self, num_slots):
        masks = []
        for d in range(5):
            for s in range(8 - num_slots + 1):
                mask = 0
                for i in range(num_slots):
                    mask |= (1 << (d * 8 + s + i))
                masks.append(mask)
        return masks

    def load_data(self, courses, rooms):
        self.courses = courses
        self.rooms = rooms
        for c in self.courses:
            # Massive Optimization: Only check rooms within the exact faculty to prevent combinatorial explosion!
            # Match building, but if is_lab strictness causes empty rooms, fallback to any room in building
            c.valid_rooms = [r for r in self.rooms if c.is_lab == r.is_lab and r.building in c.preferred_buildings]
            if not c.valid_rooms:
                c.valid_rooms = [r for r in self.rooms if r.building in c.preferred_buildings]
                
        def get_semester(code):
            match = re.search(r'\d', code)
            if match:
                digit = int(match.group())
                if digit in [1, 2, 3, 4]:
                    return digit * 2 - 1
            return 99
            
        self.courses.sort(key=lambda c: (not c.is_lab, get_semester(c.code), len(c.valid_rooms), -c.credit_hours))

    def _assign(self, course, r_id, mask):
        course.assigned_room_id = r_id
        course.assigned_slots_mask = mask
        for tid in course.instructor_ids:
            self.teacher_busy[tid] |= mask
        self.room_busy[r_id] |= mask
        for s_id in course.section_ids:
            self.section_busy[s_id] |= mask
        for i in range(40):
            if mask & (1 << i):
                for tid in course.instructor_ids:
                    self.teacher_grid[tid][i] = course
                self.room_grid[r_id][i] = course
                for s_id in course.section_ids:
                    self.section_grid[s_id][i] = course

    def _unassign(self, course, r_id, mask):
        course.assigned_room_id = -1
        course.assigned_slots_mask = 0
        for tid in course.instructor_ids:
            self.teacher_busy[tid] &= ~mask
        self.room_busy[r_id] &= ~mask
        for s_id in course.section_ids:
            self.section_busy[s_id] &= ~mask
        for i in range(40):
            if mask & (1 << i):
                for tid in course.instructor_ids:
                    self.teacher_grid[tid][i] = None
                self.room_grid[r_id][i] = None
                for s_id in course.section_ids:
                    self.section_grid[s_id][i] = None

    def _get_colliding_courses_for_slot(self, course, r_id, slot_idx):
        collisions = set()
        
        # Ignore teacher collisions for labs to prevent bottleneck if generic names (e.g. "Lab Assistant") are used heavily
        if not course.is_lab:
            for tid in course.instructor_ids:
                c_t = self.teacher_grid[tid][slot_idx]
                if c_t: collisions.add(c_t)
                
        c_r = self.room_grid[r_id][slot_idx]
        if c_r: collisions.add(c_r)
        
        for s_id in course.section_ids:
            c_s = self.section_grid[s_id][slot_idx]
            if c_s: collisions.add(c_s)
        return collisions

    def _find_best_assignment(self, course, allow_collisions=False, temperature=0.0, minimize_friday=False):
        best_r_id = -1
        best_mask = 0
        min_score = float('inf')
        best_cols = set()
        
        valid_rooms = course.valid_rooms[:]
        if temperature > 0: random.shuffle(valid_rooms)
        
        for room in valid_rooms:
            r_id = room.id
            if course.is_lab:
                req_slots = course.credit_hours
                if req_slots not in (2, 3): req_slots = 3
                masks = self.lab_masks_3 if req_slots == 3 else self.lab_masks_2
                
                if minimize_friday:
                    masks = sorted(masks, key=lambda m: 1 if (m & (0xFF << 32)) else 0)
                
                if temperature > 0: 
                    masks = list(masks)
                    random.shuffle(masks)
                
                for mask in masks:
                    cols = set()
                    for i in range(40):
                        if mask & (1 << i):
                            cols.update(self._get_colliding_courses_for_slot(course, r_id, i))
                    if not allow_collisions and cols: continue
                    
                    score = (len(cols) ** 2) * 2000
                    for c in cols:
                        if c.is_lab: score += 10000 
                        score += c.conflict_count * 500
                    if minimize_friday and (mask & (0xFF << 32)): score += 50000
                    cap_diff = room.capacity - course.num_students
                    if cap_diff < 0:
                        score += 500000 + abs(cap_diff) * 1000
                    else:
                        score += cap_diff
                    if room.building != course.preferred_buildings[0]: score += 200
                    room_load = self.room_busy[r_id].bit_count()
                    score += room_load * 5 
                    if temperature > 0: score += random.uniform(0, temperature * 100)
                    if score < min_score or (temperature > 0 and random.random() < math.exp(-(score - min_score) / temperature)):
                        min_score = score
                        best_r_id = r_id
                        best_mask = mask
                        best_cols = cols
            else:
                slot_scores = []
                for i in range(40):
                    cols = self._get_colliding_courses_for_slot(course, r_id, i)
                    if not allow_collisions and cols: continue
                    score = (len(cols) ** 2) * 2000
                    for c in cols:
                        if c.is_lab: score += 10000
                        score += c.conflict_count * 500
                    day_start = (i // 8) * 8
                    day_end = day_start + 7
                    for s_id in course.section_ids:
                        day_idx = i % 8
                        is_block1 = day_idx <= 4
                        
                        streak = 1
                        curr = i - 1
                        while curr >= day_start and (self.section_busy[s_id] & (1 << curr)):
                            if not is_block1 and curr % 8 <= 4: break
                            streak += 1
                            curr -= 1
                            
                        curr = i + 1
                        while curr <= day_end and (self.section_busy[s_id] & (1 << curr)):
                            if is_block1 and curr % 8 > 4: break
                            streak += 1
                            curr += 1
                            
                        if not minimize_friday:
                            if streak >= 3:
                                score += 400 * (streak - 2) # Heavy penalty for 3+ consecutive lectures
                            elif streak == 2:
                                score -= 150 # Reward pairs to minimize single-slot gaps
                        else:
                            if streak > 1: score -= 80 * (streak - 1) # Standard dense clustering for Friday free
                    teacher_day_load = 0
                    for tid in course.instructor_ids:
                        teacher_day_load += (self.teacher_busy[tid] & (((1 << 8) - 1) << day_start)).bit_count()
                    score += teacher_day_load * 20
                    if minimize_friday and (i >= 32): score += 50000
                    if temperature > 0: score += random.uniform(0, temperature * 50)
                    slot_scores.append((score, i, cols))
                if len(slot_scores) < course.credit_hours: continue
                chosen_slots = []
                total_cols = set()
                cap_diff = room.capacity - course.num_students
                if cap_diff < 0:
                    total_score = 500000 + abs(cap_diff) * 1000
                else:
                    total_score = cap_diff
                if room.building != course.preferred_buildings[0]: total_score += 200
                room_load = self.room_busy[r_id].bit_count()
                total_score += room_load * 5
                current_scores = list(slot_scores)
                for _ in range(course.credit_hours):
                    current_scores.sort(key=lambda x: x[0])
                    best_sc, best_slot, slot_cols = current_scores.pop(0)
                    chosen_slots.append(best_slot)
                    total_cols.update(slot_cols)
                    total_score += best_sc
                    day = best_slot // 8
                    for idx in range(len(current_scores)):
                        sc, sl, cl = current_scores[idx]
                        if sl // 8 == day:
                            current_scores[idx] = (sc + 800, sl, cl) 
                mask = sum(1 << s for s in chosen_slots)
                if total_score < min_score or (temperature > 0 and random.random() < math.exp(-(total_score - min_score) / temperature)):
                    min_score = total_score
                    best_r_id = r_id
                    best_mask = mask
                    best_cols = total_cols
        return best_r_id, best_mask, best_cols, min_score

    def solve(self, max_refinement_steps=8000, max_restarts=3, minimize_friday=False):
        for restart in range(max_restarts):
            logging.info(f"--- Start Scheduling Restart {restart + 1}/{max_restarts} ---")
            self.teacher_busy = [0] * self.num_teachers
            self.section_busy = [0] * self.num_sections
            self.room_busy = [0] * self.num_rooms
            self.teacher_grid = [[None] * 40 for _ in range(self.num_teachers)]
            self.section_grid = [[None] * 40 for _ in range(self.num_sections)]
            self.room_grid = [[None] * 40 for _ in range(self.num_rooms)]
            for c in self.courses:
                c.assigned_room_id = -1
                c.assigned_slots_mask = 0
                c.conflict_count = 0
            if restart > 0:
                for c in self.courses: random.shuffle(c.valid_rooms)
                random.shuffle(self.courses)
                def get_semester(code):
                    match = re.search(r'\d', code)
                    if match:
                        digit = int(match.group())
                        if digit in [1, 2, 3, 4]:
                            return digit * 2 - 1
                    return 99
                self.courses.sort(key=lambda c: (not c.is_lab, get_semester(c.code), len(c.valid_rooms), -c.credit_hours))
            self.unassigned_courses = []
            for course in self.courses:
                best_r_id, best_mask, _, _ = self._find_best_assignment(course, allow_collisions=False, minimize_friday=minimize_friday)
                if best_r_id != -1:
                    self._assign(course, best_r_id, best_mask)
                else:
                    self.unassigned_courses.append(course)
            if not self.unassigned_courses:
                logging.info(f"Success! Perfect schedule found on restart {restart + 1}.")
                return True
            logging.info(f"Phase 1 Complete. Entering Min-Conflicts with {len(self.unassigned_courses)} unassigned courses.")
            for step in range(max_refinement_steps):
                if not self.unassigned_courses:
                    logging.info(f"Success! Constraints resolved at iteration {step}.")
                    return True
                sample_size = min(5, len(self.unassigned_courses))
                course = max(random.sample(self.unassigned_courses, sample_size), key=lambda c: c.conflict_count)
                temp = max(0.1, 50.0 * (1.0 - step / max_refinement_steps))
                best_r_id, best_mask, best_cols, _ = self._find_best_assignment(course, allow_collisions=True, temperature=temp, minimize_friday=minimize_friday)
                if best_r_id != -1:
                    for c in best_cols:
                        c.conflict_count += 1
                        self._unassign(c, c.assigned_room_id, c.assigned_slots_mask)
                        if c not in self.unassigned_courses:
                            self.unassigned_courses.append(c)
                    self._assign(course, best_r_id, best_mask)
                    self.unassigned_courses.remove(course)
                if step % 500 == 0:
                    stuck_codes = [c.code for c in self.unassigned_courses][:10]
                    logging.info(f"Iteration {step}: {len(self.unassigned_courses)} conflicts remaining. Temp: {temp:.2f} | Stuck: {', '.join(stuck_codes)}")
        logging.warning("Scheduler failed to resolve all constraints after all restarts.")
        return False
