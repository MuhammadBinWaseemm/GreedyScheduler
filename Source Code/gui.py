import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget, QTableWidgetItem, 
                             QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QComboBox, QMessageBox, QFileDialog, QHeaderView, QLineEdit,
                             QDialog, QTextEdit, QMenu, QFormLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextDocument, QColor, QFont
from PyQt6.QtPrintSupport import QPrinter

from integrator import TimetableIntegrator

class RoomsDialog(QDialog):
    def __init__(self, default_rooms_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Rooms & Capacities")
        self.resize(700, 600)
        
        layout = QVBoxLayout(self)
        
        info = QLabel("Add, edit, or remove rooms below:")
        info.setStyleSheet("color: #00BCD4; font-size: 14px; font-weight: bold;")
        layout.addWidget(info)
        
        # Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Building", "Room Name", "Capacity", "Type", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 60)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #1E1E1E; color: #E0E0E0; border: 1px solid #333; border-radius: 8px; }
            QHeaderView::section { background-color: #121212; color: #00BCD4; font-weight: bold; padding: 5px; border: 1px solid #333; }
        """)
        layout.addWidget(self.table)
        
        # Add button
        self.btn_add = QPushButton("➕ Add Room")
        self.btn_add.setStyleSheet("background-color: #1E1E1E; color: #00BCD4; border: 1px solid #00BCD4; padding: 8px; border-radius: 5px; font-weight: bold;")
        self.btn_add.clicked.connect(self.add_empty_row)
        layout.addWidget(self.btn_add)
        
        # Populate
        for r in default_rooms_list:
            self.add_row(r.building, r.name, str(r.capacity), "Lab" if r.is_lab else "Lecture")
            
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save Config & Continue")
        self.btn_save.setStyleSheet("background-color: #00BCD4; color: #121212; padding: 10px 20px; font-weight: bold; border-radius: 5px;")
        self.btn_save.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        
        layout.addLayout(btn_layout)
        
    def add_row(self, building, name, capacity, r_type):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        self.table.setItem(row, 0, QTableWidgetItem(building))
        self.table.setItem(row, 1, QTableWidgetItem(name))
        self.table.setItem(row, 2, QTableWidgetItem(capacity))
        
        type_combo = QComboBox()
        type_combo.addItems(["Lecture", "Lab"])
        type_combo.setCurrentText(r_type)
        type_combo.setStyleSheet("background-color: #2E2E2E; color: white;")
        self.table.setCellWidget(row, 3, type_combo)
        
        btn_del = QPushButton("❌")
        btn_del.setStyleSheet("background-color: transparent; border: none; font-size: 16px;")
        btn_del.clicked.connect(self.remove_row_by_button)
        self.table.setCellWidget(row, 4, btn_del)

    def remove_row_by_button(self):
        button = self.sender()
        if button:
            index = self.table.indexAt(button.pos())
            if index.isValid():
                self.table.removeRow(index.row())

    def add_empty_row(self, *args):
        self.add_row("New Building", "New Room", "100", "Lecture")
        
    def get_custom_rooms(self):
        from excel_parser import RoomData
        rooms = []
        for row in range(self.table.rowCount()):
            b_item = self.table.item(row, 0)
            n_item = self.table.item(row, 1)
            c_item = self.table.item(row, 2)
            combo = self.table.cellWidget(row, 3)
            
            if not b_item or not n_item or not c_item: continue
            
            building = b_item.text().strip()
            name = n_item.text().strip()
            if not name or not building: continue
            
            try: capacity = int(c_item.text().strip())
            except: capacity = 60
            
            is_lab = (combo.currentText() == "Lab")
            
            rooms.append(RoomData(name, building, capacity=capacity, is_lab=is_lab))
            
        return rooms

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timetable Generator - Modern UI")
        self.resize(1280, 720)
        
        self.integrator = TimetableIntegrator()
        self.timetable_data = [] # Stores structured pipeline output
        self.unique_sections = []
        self.unique_buildings = []
        self.unique_teachers = []
        self.current_view_mode = 'section'
        self.custom_rooms = None
        self.excel_file = None
        self.rooms_excel_file = None
        self.setup_ui()
        self.apply_theme()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        mainLayout = QHBoxLayout(central)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.setSpacing(0)
        
        # Sidebar Navigation
        sideNav = QWidget()
        sideNav.setFixedWidth(260)
        sideNav.setObjectName("sideNav")
        navLayout = QVBoxLayout(sideNav)
        navLayout.setContentsMargins(20, 30, 20, 30)
        navLayout.setSpacing(20)
        
        title = QLabel("TIMETABLE\nSYSTEM")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("appTitle")
        navLayout.addWidget(title)
        
        # Two import buttons side by side
        importLayout = QHBoxLayout()
        importLayout.setSpacing(8)
        self.btnImportCourses = QPushButton("📂 Courses")
        self.btnImportRooms = QPushButton("📂 Rooms")
        for btn in (self.btnImportCourses, self.btnImportRooms):
            btn.setMinimumHeight(44)
        importLayout.addWidget(self.btnImportCourses)
        importLayout.addWidget(self.btnImportRooms)

        self.btnGenerate = QPushButton("📅 Generate Timetable")
        self.btnFridayFree = QPushButton("🏖️ Friday Free")
        self.btnSectionView = QPushButton("👨‍🎓 View Section Timetable")
        self.btnBuildingView = QPushButton("🏢 View Building Timetable")
        self.btnTeacherView = QPushButton("👨‍🏫 View Teacher Timetable")
        self.btnExportPdf = QPushButton("📄 Export PDF")
        self.btnExportExcel = QPushButton("📊 Export Excel")
        
        navLayout.addLayout(importLayout)
        navLayout.addWidget(self.btnGenerate)
        navLayout.addWidget(self.btnFridayFree)
        navLayout.addWidget(self.btnSectionView)
        navLayout.addWidget(self.btnBuildingView)
        navLayout.addWidget(self.btnTeacherView)
        navLayout.addStretch()
        navLayout.addWidget(self.btnExportPdf)
        navLayout.addWidget(self.btnExportExcel)
        
        mainLayout.addWidget(sideNav)
        
        # Main Content Area
        content = QWidget()
        contentLayout = QVBoxLayout(content)
        contentLayout.setContentsMargins(30, 30, 30, 30)
        contentLayout.setSpacing(20)
        
        # Top Bar (Dropdown & Search)
        topBar = QHBoxLayout()
        topBar.setSpacing(15)
        
        self.previewLabel = QLabel("Preview Section:")
        self.previewLabel.setStyleSheet("color: #00BCD4; font-weight: bold; font-size: 16px;")
        
        self.sectionCombo = QComboBox()
        self.sectionCombo.setMinimumHeight(45)
        self.sectionCombo.setMinimumWidth(250)
        
        self.searchEdit = QLineEdit()
        self.searchEdit.setPlaceholderText("🔍 Search teacher, course, room...")
        self.searchEdit.setMinimumHeight(45)
        
        topBar.addWidget(self.previewLabel)
        topBar.addWidget(self.sectionCombo)
        topBar.addStretch()
        topBar.addWidget(self.searchEdit)
        
        # Grid View (5x8)
        self.table = QTableWidget(5, 8)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setVerticalHeaderLabels(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
        self.table.setHorizontalHeaderLabels([
            "8:00-8:50", "9:00-9:50", "10:30-11:20", "11:30-12:20", 
            "12:30-1:20", "2:30-3:20", "3:30-4:20", "4:30-5:20"
        ])
        
        contentLayout.addLayout(topBar)
        contentLayout.addWidget(self.table)
        
        mainLayout.addWidget(content)
        
        # Event Connections
        self.btnImportCourses.clicked.connect(self.import_courses_excel)
        self.btnImportRooms.clicked.connect(self.import_rooms_excel)
        self.btnGenerate.clicked.connect(self.generate_timetable)
        self.btnFridayFree.clicked.connect(self.generate_friday_free)
        self.btnSectionView.clicked.connect(lambda: self.set_view_mode('section'))
        self.btnBuildingView.clicked.connect(lambda: self.set_view_mode('building'))
        self.btnTeacherView.clicked.connect(lambda: self.set_view_mode('teacher'))
        self.btnExportPdf.clicked.connect(self.export_pdf)
        self.btnExportExcel.clicked.connect(self.export_excel)
        self.sectionCombo.currentTextChanged.connect(self.on_filter_changed)
        self.searchEdit.textChanged.connect(self.on_filter_changed)
        
        # State Management
        self.btnGenerate.setEnabled(False)
        self.btnFridayFree.setEnabled(False)
        self.btnSectionView.setEnabled(False)
        self.btnBuildingView.setEnabled(False)
        self.btnTeacherView.setEnabled(False)
        self.btnExportPdf.setEnabled(False)
        self.btnExportExcel.setEnabled(False)

    def on_filter_changed(self):
        self.reschedule_state = None
        self.populate_grid()

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            #sideNav { background-color: #1A1A1A; border-right: 1px solid #333; }
            #appTitle { color: #00BCD4; font-size: 24px; font-weight: 900; letter-spacing: 2px; }
            
            QPushButton {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border: 1px solid #3A3A3A;
                border-radius: 8px;
                padding: 12px 18px;
                font-size: 15px;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #00BCD4;
                color: #121212;
                border: 1px solid #00BCD4;
            }
            QPushButton:pressed { background-color: #008BA3; }
            QPushButton:disabled { background-color: #1A1A1A; color: #555; border: 1px solid #222; }
            
            QComboBox, QLineEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 8px 15px;
                font-size: 15px;
            }
            QComboBox:focus, QLineEdit:focus { border: 1px solid #00BCD4; }
            
            QTableWidget {
                background-color: #1A1A1A;
                color: #E0E0E0;
                border: 1px solid #333;
                border-radius: 8px;
                gridline-color: #333333;
            }
            QHeaderView::section {
                background-color: #121212;
                color: #00BCD4;
                padding: 12px;
                border: 1px solid #333;
                font-size: 14px;
                font-weight: bold;
            }
        """)

    def import_courses_excel(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open Courses Excel File", "", "Excel Files (*.xlsx *.xls)")
        if fileName:
            self.excel_file = fileName
            self._check_ready_to_generate()
            QMessageBox.information(self, "Courses Loaded", "Courses Excel loaded successfully!")

    def import_rooms_excel(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open Rooms Excel File", "", "Excel Files (*.xlsx *.xls)")
        if fileName:
            self.rooms_excel_file = fileName
            # Parse rooms from excel and skip the manual dialog
            from excel_parser import TimetableExcelParser, RoomData
            parser = TimetableExcelParser()
            # Read the rooms excel: columns are #, Building, Room Name, Type
            import pandas as pd
            try:
                df = pd.read_excel(fileName)
                df.columns = df.columns.astype(str).str.strip()
                rooms = []
                for _, row in df.iterrows():
                    building = str(row.get('Building', '')).strip()
                    name = str(row.get('Room Name', '')).strip()
                    r_type = str(row.get('Type', 'Lecture')).strip()
                    if not name or not building or name.lower() in ('nan', 'none'):
                        continue
                    is_lab = (r_type.lower() == 'lab')
                    rooms.append(RoomData(name, building, capacity=60, is_lab=is_lab))
                self.custom_rooms = rooms
                self._check_ready_to_generate()
                QMessageBox.information(self, "Rooms Loaded", f"Rooms Excel loaded: {len(rooms)} rooms found!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load rooms:\n{e}")

    def _check_ready_to_generate(self):
        if self.excel_file:
            self.btnGenerate.setEnabled(True)
            self.btnFridayFree.setEnabled(True)

    def import_excel(self):
        # Legacy fallback — kept for compatibility
        self.import_courses_excel()

    def generate_timetable(self):
        if not self.excel_file: return
        if not self.custom_rooms:
            default_rooms = self.integrator.get_default_rooms()
            dialog = RoomsDialog(default_rooms, self)
            if dialog.exec():
                self.custom_rooms = dialog.get_custom_rooms()
            else:
                return
        self.btnGenerate.setText("⏳ Generating...")
        QApplication.processEvents()
        
        self.timetable_data = self.integrator.generate_timetable(self.excel_file, self.excel_file, custom_rooms=self.custom_rooms)
        
        self.btnGenerate.setText("📅 Generate Timetable")
        self._post_generate()

    def generate_friday_free(self):
        if not self.excel_file: return
        if not self.custom_rooms:
            default_rooms = self.integrator.get_default_rooms()
            dialog = RoomsDialog(default_rooms, self)
            if dialog.exec():
                self.custom_rooms = dialog.get_custom_rooms()
            else:
                return
        self.btnFridayFree.setText("⏳ Generating...")
        QApplication.processEvents()
        
        self.timetable_data = self.integrator.generate_timetable(self.excel_file, self.excel_file, minimize_friday=True, custom_rooms=self.custom_rooms)
        
        self.btnFridayFree.setText("🏖️ Friday Free")
        self._post_generate()

    def _post_generate(self):
        if isinstance(self.timetable_data, str):
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Scheduler Failed")
            msg.setText("Could not resolve constraints for some courses.")
            msg.setInformativeText("Click 'Show Details' to view the specific collisions.")
            msg.setDetailedText(self.timetable_data)
            msg.exec()
            self.timetable_data = None
            return
            
        if self.timetable_data is None:
            QMessageBox.warning(self, "Warning", "Could not resolve constraints. Check Excel capacity/rules.")
            return
            
        # Extract unique sections and buildings for dropdown
        sections = set()
        buildings = set()
        teachers = set()
        for c in self.timetable_data:
            for s in c.get('sections', []):
                sections.add(s)
            if c.get('building'):
                buildings.add(c['building'])
            if c.get('instructors'):
                for t in c['instructors']:
                    teachers.add(t)
            elif c.get('instructor'):
                teachers.add(c['instructor'])
                
        self.unique_sections = sorted(list(sections))
        self.unique_buildings = sorted(list(buildings))
        self.unique_teachers = sorted(list(teachers))
        
        self.sectionCombo.blockSignals(True)
        self.sectionCombo.clear()
        if self.current_view_mode == 'section':
            self.sectionCombo.addItems(self.unique_sections)
        elif self.current_view_mode == 'building':
            self.sectionCombo.addItems(self.unique_buildings)
        elif self.current_view_mode == 'teacher':
            self.sectionCombo.addItems(self.unique_teachers)
        self.sectionCombo.blockSignals(False)
        
        self.btnSectionView.setEnabled(True)
        self.btnBuildingView.setEnabled(True)
        self.btnTeacherView.setEnabled(True)
        self.btnExportPdf.setEnabled(True)
        self.btnExportExcel.setEnabled(True)
        
        self.populate_grid()
        QMessageBox.information(self, "Success", "Timetable generated via CSP Backend successfully!")

    def set_view_mode(self, mode):
        self.reschedule_state = None
        self.current_view_mode = mode
        
        self.sectionCombo.blockSignals(True)
        self.sectionCombo.clear()
        
        if mode == 'section':
            self.previewLabel.setText("Preview Section:")
            self.sectionCombo.addItems(self.unique_sections)
        elif mode == 'building':
            self.previewLabel.setText("Preview Building:")
            self.sectionCombo.addItems(self.unique_buildings)
        elif mode == 'teacher':
            self.previewLabel.setText("Preview Teacher:")
            self.sectionCombo.addItems(self.unique_teachers)
            
        self.sectionCombo.blockSignals(False)
        self.populate_grid()

    def populate_grid(self):
        filter_val = self.sectionCombo.currentText()
        search_query = self.searchEdit.text().lower()
        
        if not self.timetable_data: return
        
        days_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4}
        days_list = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        slots_labels = ["8:00-8:50", "9:00-9:50", "10:30-11:20", "11:30-12:20", 
                        "12:30-1:20", "2:30-3:20", "3:30-4:20", "4:30-5:20"]
        
        if self.current_view_mode == 'section':
            self.table.clearSpans()
            self.table.setRowCount(5)
            self.table.setColumnCount(8)
            self.table.verticalHeader().setVisible(True)
            self.table.setVerticalHeaderLabels(days_list)
            self.table.setHorizontalHeaderLabels(slots_labels)
            
            for r in range(5):
                for c in range(8):
                    self.table.setItem(r, c, QTableWidgetItem(""))
                    
            for c_idx, c in enumerate(self.timetable_data):
                if filter_val not in c.get('sections', []):
                    continue
                    
                search_target = f"{c['course_code']} {c['course_title']} {c['instructor']} {c['room']}".lower()
                if search_query and search_query not in search_target:
                    continue
                    
                text = f"{c['course_code']}\n{c['room']}\n({c['instructor']})"
                
                for s_idx_in_schedule, slot in enumerate(c['schedule']):
                    d_idx = days_map.get(slot['day'])
                    s_idx = slot['slot_index']
                    
                    if d_idx is not None:
                        item = QTableWidgetItem(text)
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        item.setBackground(QColor("#1E1E1E"))
                        item.setForeground(QColor("#FFFFFF"))
                        if search_query:
                            item.setBackground(QColor("#00BCD4"))
                            item.setForeground(QColor("#121212"))
                        item.setData(Qt.ItemDataRole.UserRole, {"course_idx": c_idx, "slot_index": s_idx_in_schedule})
                        self.table.setItem(d_idx, s_idx, item)
        
        elif self.current_view_mode == 'building':
            rooms = sorted(list(set(c['room'] for c in self.timetable_data if c.get('building') == filter_val)))
            if not rooms:
                self.table.setRowCount(0)
                return
                
            self.table.clearSpans()
            self.table.setRowCount(5 * len(rooms))
            self.table.setColumnCount(10)
            self.table.verticalHeader().setVisible(False)
            self.table.setHorizontalHeaderLabels(["Day", "Room"] + slots_labels)
            
            # Initialize empty grid with Day and Room labels
            row_idx = 0
            for day in days_list:
                start_row = row_idx
                for room in rooms:
                    for col in range(2, 10):
                        self.table.setItem(row_idx, col, QTableWidgetItem(""))
                    
                    if row_idx == start_row:
                        day_item = QTableWidgetItem(day)
                        day_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        day_item.setBackground(QColor("#121212"))
                        day_item.setForeground(QColor("#00BCD4"))
                        self.table.setItem(row_idx, 0, day_item)
                        
                    room_item = QTableWidgetItem(room)
                    room_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    room_item.setBackground(QColor("#1A1A1A"))
                    self.table.setItem(row_idx, 1, room_item)
                    row_idx += 1
                    
                if len(rooms) > 1:
                    self.table.setSpan(start_row, 0, len(rooms), 1)
                    
            # Populate courses
            for c_idx, c in enumerate(self.timetable_data):
                if c.get('building') != filter_val:
                    continue
                    
                search_target = f"{c['course_code']} {c['course_title']} {c['instructor']} {c['room']}".lower()
                if search_query and search_query not in search_target:
                    continue
                    
                text = f"{c['course_code']}\n{', '.join(c.get('sections', []))}\n({c['instructor']})"
                
                for s_idx_in_schedule, slot in enumerate(c['schedule']):
                    if slot['day'] not in days_map or c['room'] not in rooms:
                        continue
                        
                    day_idx = days_map[slot['day']]
                    room_idx = rooms.index(c['room'])
                    r = (day_idx * len(rooms)) + room_idx
                    s_idx = slot['slot_index'] + 2
                    
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setBackground(QColor("#2C3E50"))
                    item.setForeground(QColor("#FFFFFF"))
                    if search_query:
                        item.setBackground(QColor("#00BCD4"))
                        item.setForeground(QColor("#121212"))
                    item.setData(Qt.ItemDataRole.UserRole, {"course_idx": c_idx, "slot_index": s_idx_in_schedule})
                    self.table.setItem(r, s_idx, item)

        elif self.current_view_mode == 'teacher':
            self.table.clearSpans()
            self.table.setRowCount(5)
            self.table.setColumnCount(8)
            self.table.verticalHeader().setVisible(True)
            self.table.setVerticalHeaderLabels(days_list)
            self.table.setHorizontalHeaderLabels(slots_labels)
            
            for r in range(5):
                for c in range(8):
                    self.table.setItem(r, c, QTableWidgetItem(""))
                    
            for c_idx, c in enumerate(self.timetable_data):
                inst_list = c.get('instructors', [c.get('instructor')])
                if filter_val not in inst_list:
                    continue
                    
                search_target = f"{c['course_code']} {c['course_title']} {c.get('room', '')}".lower()
                if search_query and search_query not in search_target:
                    continue
                    
                text = f"{c['course_code']}\n{c.get('room', '')}\n({', '.join(c.get('sections', []))})"
                
                for s_idx_in_schedule, slot in enumerate(c['schedule']):
                    d_idx = days_map.get(slot['day'])
                    s_idx = slot['slot_index']
                    
                    if d_idx is not None:
                        item = QTableWidgetItem(text)
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        item.setBackground(QColor("#1E1E1E"))
                        item.setForeground(QColor("#FFFFFF"))
                        if search_query:
                            item.setBackground(QColor("#00BCD4"))
                            item.setForeground(QColor("#121212"))
                        item.setData(Qt.ItemDataRole.UserRole, {"course_idx": c_idx, "slot_index": s_idx_in_schedule})
                        self.table.setItem(d_idx, s_idx, item)

        if getattr(self, 'reschedule_state', None):
            c_idx = self.reschedule_state['course_idx']
            s_idx = self.reschedule_state['slot_index']
            course = self.timetable_data[c_idx]
            clicked_slot = course['schedule'][s_idx]
            is_lab = course.get('is_lab', False) or str(course.get('course_code', '')).upper().endswith('L')
            
            if is_lab:
                related_slots = [s for s in course['schedule'] if s['day'] == clicked_slot['day']]
                related_slots.sort(key=lambda x: x['slot_index'])
                num_slots = len(related_slots)
            else:
                num_slots = 1
                
            my_teachers = set(course.get('instructors', []))
            if not my_teachers and course.get('instructor'):
                my_teachers = set([course.get('instructor')])
            my_sections = set(course.get('sections', []))
            
            orig_room = course.get('room')
            if self.current_view_mode == 'building':
                rooms = sorted(list(set(c['room'] for c in self.timetable_data if c.get('building') == filter_val)))
            else:
                rooms = []

            def check_clash(day, sl_idx, room, exclude_c_idx):
                t_clash, s_clash, r_clash = False, False, False
                for i, other_c in enumerate(self.timetable_data):
                    if i == exclude_c_idx: continue
                    for s in other_c['schedule']:
                        if s['day'] == day and s['slot_index'] == sl_idx:
                            if room and other_c.get('room') == room: r_clash = True
                            c_t = set(other_c.get('instructors', []))
                            if not c_t and other_c.get('instructor'): c_t.add(other_c.get('instructor'))
                            if my_teachers.intersection(c_t): t_clash = True
                            c_s = set(other_c.get('sections', []))
                            if my_sections.intersection(c_s): s_clash = True
                return t_clash, s_clash, r_clash

            for row in range(self.table.rowCount()):
                for col in range(self.table.columnCount()):
                    if self.current_view_mode == 'building' and col < 2: continue
                    
                    if self.current_view_mode == 'building':
                        if not rooms: continue
                        day_name = days_list[row // len(rooms)]
                        room_name = rooms[row % len(rooms)]
                        slot_index = col - 2
                        rooms_to_check = [room_name]
                    else:
                        day_name = days_list[row]
                        slot_index = col
                        room_name = orig_room
                        
                        rooms_list = self.custom_rooms if self.custom_rooms else self.integrator.get_default_rooms()
                        rooms_to_check = [r.name for r in rooms_list if r.is_lab == is_lab]
                        
                    out_of_bounds = False
                    t_clash_total, s_clash_total = False, False
                    all_rooms_occupied = False
                    best_room = None
                    
                    if slot_index + num_slots > 8:
                        out_of_bounds = True
                    else:
                        for offset in range(num_slots):
                            tc, sc, _ = check_clash(day_name, slot_index + offset, "", c_idx)
                            if tc: t_clash_total = True
                            if sc: s_clash_total = True
                            
                        if not t_clash_total and not s_clash_total:
                            found_free_room = False
                            if orig_room in rooms_to_check:
                                rooms_to_check.remove(orig_room)
                                rooms_to_check.insert(0, orig_room)
                                
                            for r_name in rooms_to_check:
                                r_clash = False
                                for offset in range(num_slots):
                                    _, _, rc = check_clash(day_name, slot_index + offset, r_name, c_idx)
                                    if rc:
                                        r_clash = True
                                        break
                                if not r_clash:
                                    found_free_room = True
                                    best_room = r_name
                                    break
                                    
                            if not found_free_room:
                                all_rooms_occupied = True
                            
                    item = self.table.item(row, col)
                    if not item:
                        item = QTableWidgetItem("")
                        self.table.setItem(row, col, item)
                        
                    if out_of_bounds:
                        item.setBackground(QColor("#4A0000"))
                        clash_msg = "Out of Bounds"
                        target_room = orig_room
                    elif t_clash_total or s_clash_total or all_rooms_occupied:
                        item.setBackground(QColor("#4A0000"))
                        msgs = []
                        if t_clash_total: msgs.append("Teacher Clash")
                        if s_clash_total: msgs.append("Section Clash")
                        if all_rooms_occupied: msgs.append("All Rooms Occupied")
                        clash_msg = " & ".join(msgs)
                        target_room = orig_room
                    else:
                        item.setBackground(QColor("#004A00"))
                        clash_msg = None
                        target_room = best_room
                        
                    target_data = {
                        "is_target_cell": True,
                        "day": day_name,
                        "slot_index": slot_index,
                        "room": target_room,
                        "clash_msg": clash_msg
                    }
                    item.setData(Qt.ItemDataRole.UserRole + 1, target_data)
                    
                    if clash_msg:
                        item.setToolTip(clash_msg)
                    else:
                        item.setToolTip("Available (Right-click to select room)")

    def export_pdf(self):
        if not getattr(self, 'timetable_data', None):
            QMessageBox.warning(self, "Warning", "No timetable data generated yet.")
            return
            
        fileName, _ = QFileDialog.getSaveFileName(self, "Export PDF", "Timetables.pdf", "PDF Files (*.pdf)")
        if not fileName: return
        
        import importlib
        import export_manager
        importlib.reload(export_manager)
        from export_manager import ExportManager
        
        manager = ExportManager(self.timetable_data, mode=self.current_view_mode)
        try:
            manager.export_pdf(fileName)
            QMessageBox.information(self, "Success", "Exported to PDF successfully!")
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "Error", f"Failed to export PDF:\n{traceback.format_exc()}")

    def export_excel(self):
        if not getattr(self, 'timetable_data', None):
            QMessageBox.warning(self, "Warning", "No timetable data generated yet.")
            return
            
        fileName, _ = QFileDialog.getSaveFileName(self, "Export Excel", "Timetables.xlsx", "Excel Files (*.xlsx)")
        if not fileName: return
        
        import importlib
        import export_manager
        importlib.reload(export_manager)
        from export_manager import ExportManager
        
        manager = ExportManager(self.timetable_data, mode=self.current_view_mode)
        try:
            manager.export_excel(fileName)
            QMessageBox.information(self, "Success", "Exported to Excel successfully! (Used CSV fallback if openpyxl was missing)")
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "Error", f"Failed to export Excel:\n{traceback.format_exc()}")

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item: return
        data = item.data(Qt.ItemDataRole.UserRole)
        target_data = item.data(Qt.ItemDataRole.UserRole + 1)
        
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1E1E1E; color: white; border: 1px solid #333; } QMenu::item:selected { background-color: #00BCD4; color: black; }")
        
        if getattr(self, 'reschedule_state', None):
            cancel_action = menu.addAction("Cancel Reschedule")
            move_action = None
            if target_data and target_data.get('is_target_cell'):
                if target_data['clash_msg']:
                    move_action = menu.addAction(f"Force Move Here ({target_data['clash_msg']})")
                else:
                    move_action = menu.addAction("Confirm Move Here")
            
            action = menu.exec(self.table.viewport().mapToGlobal(pos))
            if action == cancel_action:
                self.reschedule_state = None
                self.populate_grid()
            elif move_action and action == move_action:
                self.handle_move_here(target_data)
        else:
            if not data or 'course_idx' not in data: return
            reschedule_action = menu.addAction("Reschedule this class")
            action = menu.exec(self.table.viewport().mapToGlobal(pos))
            if action == reschedule_action:
                self.reschedule_state = data
                self.populate_grid()

    def handle_move_here(self, target_data):
        if target_data['clash_msg']:
            reply = QMessageBox.question(self, "Force Move", 
                f"There is a clash: {target_data['clash_msg']}.\nAre you sure you want to force this move?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
                
        c_idx = self.reschedule_state['course_idx']
        s_idx = self.reschedule_state['slot_index']
        course = self.timetable_data[c_idx]
        clicked_slot = course['schedule'][s_idx]
        is_lab = course.get('is_lab', False) or str(course.get('course_code', '')).upper().endswith('L')
        
        if is_lab:
            related_slots = [s for s in course['schedule'] if s['day'] == clicked_slot['day']]
            related_slots.sort(key=lambda x: x['slot_index'])
            num_slots = len(related_slots)
        else:
            related_slots = [clicked_slot]
            num_slots = 1
            
        new_day = target_data['day']
        new_start_idx = target_data['slot_index']
        
        rooms_list = self.custom_rooms if self.custom_rooms else self.integrator.get_default_rooms()
        valid_rooms = [r for r in rooms_list if r.is_lab == is_lab]
        
        occupied_rooms = set()
        req_indices = list(range(new_start_idx, new_start_idx + num_slots))
        for i, c in enumerate(self.timetable_data):
            if i == c_idx: continue
            for s in c['schedule']:
                if s['day'] == new_day and s['slot_index'] in req_indices:
                    occupied_rooms.add(c.get('room'))
                    
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Room")
        dialog.setStyleSheet("QDialog { background-color: #121212; color: #E0E0E0; } QLabel { color: #E0E0E0; font-size: 14px; }")
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel(f"Select an available room for {new_day}:"))
        
        combo = QComboBox()
        combo.setStyleSheet("background-color: #1E1E1E; color: white; padding: 5px;")
        
        for r in valid_rooms:
            if r.name not in occupied_rooms:
                combo.addItem(r.name, userData=r.building)
                
        if combo.count() == 0:
            combo.addItem("No available rooms!")
            combo.setEnabled(False)
            
        target_room_name = target_data.get('room')
        if target_room_name:
            idx = combo.findText(target_room_name, Qt.MatchFlag.MatchContains)
            if idx >= 0:
                combo.setCurrentIndex(idx)
                
        layout.addWidget(combo)
        
        btn_box = QHBoxLayout()
        btn_ok = QPushButton("Confirm Move")
        btn_ok.setStyleSheet("background-color: #00BCD4; color: #121212; font-weight: bold; padding: 8px;")
        if combo.count() == 1 and combo.currentText() == "No available rooms!":
            btn_ok.setEnabled(False)
            btn_ok.setStyleSheet("background-color: #555; color: #888; font-weight: bold; padding: 8px;")
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("background-color: #333; color: white; padding: 8px;")
        
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)
        
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        selected_text = combo.currentText()
        new_room_name = selected_text.split(" (")[0]
        new_bldg = combo.currentData()
        
        slots_labels = ["8:00-8:50", "9:00-9:50", "10:30-11:20", "11:30-12:20", "12:30-1:20", "2:30-3:20", "3:30-4:20", "4:30-5:20"]
        
        for s in related_slots:
            if s in course['schedule']:
                course['schedule'].remove(s)
                
        new_slots = []
        for i in range(num_slots):
            new_idx = new_start_idx + i
            new_slots.append({'day': new_day, 'time': slots_labels[new_idx], 'slot_index': new_idx})
            
        if new_room_name == course.get('room'):
            course['schedule'].extend(new_slots)
        else:
            import copy
            new_course = copy.deepcopy(course)
            new_course['room'] = new_room_name
            new_course['building'] = new_bldg
            new_course['schedule'] = new_slots
            self.timetable_data.append(new_course)
            
        self.reschedule_state = None
        self.populate_grid()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
