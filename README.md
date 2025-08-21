# Smart Attendance System  

## 📌 Overview  
The **Smart Attendance System** is a face-recognition-based web application built using **Flask** and **MongoDB**. It automates student attendance management and provides separate portals for **Admin**, **Teacher**, and **Student**.  

- ✅ **Admin** can register students/teachers, manage attendance, update face data, and generate academic reports.  
- ✅ **Teachers** can take attendance, generate subject/class reports, and manage sessions.  
- ✅ **Students** can log in to view their attendance reports and eligibility status.  

This system ensures transparency, reduces manual errors, and improves attendance management efficiency.  

---

## 🚀 Features  

### 👨‍💼 Admin Portal  
- Dashboard overview  
- Register students with face capture  
- Register teachers with subject & class assignment  
- Manage users & face data updates  
- Attendance overview with edit options  
- Generate academic reports (IA1, IA2, IA3, SEE)  
- Update exam dates  

### 👩‍🏫 Teacher Portal  
- Face-recognition-based login  
- Take attendance by class & subject  
- Generate subject-wise attendance reports  

### 👨‍🎓 Student Portal  
- Login with ID & password  
- View attendance report  
- Check attendance percentage & eligibility  

---

## 🛠️ Tech Stack  

- **Backend:** Python (Flask)  
- **Database:** MongoDB  
- **Frontend:** HTML, CSS, Bootstrap  
- **Face Recognition:** OpenCV, face_recognition library  
- **Reports:** Excel & HTML-based reports  

---

## 📂 Project Structure  

```
smart_attendance/
│── admin/              # Admin portal
│   ├── admin_app.py
│   ├── templates/      # Admin HTML pages
│   ├── static/         # CSS, JS, assets
│   └── admin_reports/  # Generated reports
│
│── teacher/            # Teacher portal
│   ├── teacher_app.py
│   └── attendance_pics/  # Captured images
│
│── student/            # Student portal
│   ├── student_app.py
│   └── templates/      # Student HTML pages
│
│── requirements.txt    # Python dependencies
│── README.md           # Project documentation
```

---

## ⚙️ Installation & Setup  

1. **Clone the Repository**  
   ```bash
   git clone https://github.com/your-username/smart_attendance.git
   cd smart_attendance
   ```

2. **Create Virtual Environment & Install Dependencies**  
   ```bash
   python -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Start MongoDB**  
   Ensure MongoDB service is running locally (default: `mongodb://localhost:27017/`).  

4. **Run Applications**  
   - Admin Portal:  
     ```bash
     python admin/admin_app.py
     ```
   - Teacher Portal:  
     ```bash
     python teacher/teacher_app.py
     ```
   - Student Portal:  
     ```bash
     python student/student_app.py
     ```

---

## 📊 Academic Report Criteria  
- **IA1:** 65% attendance required  
- **IA2:** 75% attendance required  
- **IA3:** 85% attendance required  
- **SEE:** 75% attendance required  

---

## 🤝 Contributing  
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.  

---

## 📜 License  
This project is licensed under the MIT License.  
