# GreedyScheduler

GreedyScheduler is a modern, high-performance University Timetable Generator and Interactive Simulator. Built with a responsive **PyQt6** dark-mode interface, it uses an advanced Constraint Satisfaction Problem (CSP) backend to automatically schedule complex university constraints—including multi-slot labs, instructor availability, student sections, and room capacities—without creating collisions. 

It also includes a powerful **Interactive Rescheduling Engine**, allowing administrators to manually drag, drop, and force-move classes using a visual heat-map that perfectly tracks instructor and student availability in real-time.

## ✨ Features

- **Smart Constraint Engine:** Automatically resolves clashes between teachers, rooms, and sections. Treats lab courses as contiguous multi-hour blocks.
- **"Friday Free" Mode:** An aggressive optimization mode that attempts to compress the university schedule into Monday–Thursday, leaving Fridays as free as possible.
- **Interactive Heat-Map Rescheduling:** Right-click any course to enter "Reschedule Mode". The grid instantly highlights available, collision-free slots in **Green**, and blocked slots in **Red**.
- **Real-Time Collision Feedback:** Hovering over a blocked slot tells you exactly why it failed (e.g., "Teacher Clash", "Section Clash", or "All Rooms Occupied").
- **Multi-Perspective Views:** Filter the generated timetable by **Section**, **Building**, or **Teacher**. 
- **Universal Search:** Instantly filter courses via the live search bar by course code, title, room, or instructor name.
- **Export Capabilities:** Export the finalized timetables directly to **PDF** or **Excel (.xlsx)** formats.

## 🚀 Installation

Ensure you have Python 3.9+ installed.

1. Clone the repository:
   ```bash
   git clone https://github.com/MuhammadBinWaseemm/GreedyScheduler.git
   cd GreedyScheduler
   ```

2. Install the required dependencies:
   ```bash
   pip install PyQt6 pandas openpyxl reportlab
   ```

## 🎮 How to Use the Simulator

1. **Launch the Application:**
   Run the main GUI file to start the simulator.
   ```bash
   python gui.py
   ```

2. **Import Data:**
   - Click the **"📂 Courses"** button and select your master courses Excel file.
   - Click the **"📂 Rooms"** button and select your master rooms Excel file.

3. **Generate Timetable:**
   - Click **"📅 Generate Timetable"** to run the standard CSP solver.
   - *Alternatively*, click **"🏖️ Friday Free"** to instruct the solver to prioritize a 4-day workweek.

4. **Navigate Views:**
   - Use the **View Section**, **View Building**, or **View Teacher** buttons on the sidebar to change perspectives.
   - Use the dropdown menu at the top to select specific target groups.

5. **Interactive Rescheduling (Manual Overrides):**
   - In any view, **Right-Click** a scheduled course and select **"Reschedule this class"**.
   - The grid will turn into a heat-map. 
   - **Green Slots** are safe. Right-click a green slot to pick an available room and confirm the move.
   - **Red Slots** have a clash. If you must force a collision, right-click the red slot, and the system will explicitly warn you of the consequences before allowing the override.
   - Changing the dropdown filter or typing in the search bar will automatically cancel Reschedule Mode for safety.

6. **Exporting:**
   - Once satisfied, use the **"📄 Export PDF"** or **"📊 Export Excel"** buttons to save the master timetables to your machine.

## 📁 Required Excel Formats

To ensure the engine parses your data correctly, your Excel files should follow these formats:

**Courses Excel (Expected Columns):**
- `Course Code` (e.g., CS101. Labs must end in 'L', e.g., CS101L)
- `Course Title`
- `Credit Hours` (Labs should be 1 credit hour = 3 time slots)
- `Section` (Comma-separated if combined, e.g., "BCS-2A, BCS-2B")
- `Instructor` (Comma-separated for co-teachers)
- `Type` (Core / Elective)

**Rooms Excel (Expected Columns):**
- `#` (Index)
- `Building` (e.g., AcB, FCSE)
- `Room Name` (e.g., LH1, Lab 2)
- `Type` (Lecture or Lab)

## 🛠️ Architecture
- `gui.py`: The PyQt6 interactive frontend and manual rescheduling logic.
- `scheduler_engine.py`: The core CSP / Min-Conflicts solver algorithm.
- `integrator.py`: The bridge that passes GUI commands and file paths to the solver.
- `excel_parser.py`: Handles data ingestion and strict data cleaning using `pandas`.
- `export_manager.py`: Handles formatting and layout generation for PDF/Excel exports.

---
*Created by [MuhammadBinWaseemm](https://github.com/MuhammadBinWaseemm)*
