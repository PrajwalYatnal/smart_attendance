from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, send_file
from pymongo import MongoClient
import cv2
import base64
import face_recognition
import numpy as np
import datetime
import csv
from bson import ObjectId
import os
import time
from bson.objectid import ObjectId
from collections import defaultdict
import pandas as pd

app = Flask(__name__)
app.secret_key = os.urandom(24)

# MongoDB Setup
client = MongoClient("mongodb://localhost:27017/")
db = client["face_db"]
teachers = db["teachers"]
students = db["students"]
class_sessions = db["class_sessions"]
attendance_db = db["attendance"]

def generate_frames():
    """Generate webcam frames for streaming to the frontend."""
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # Convert the frame to JPEG for streaming to HTML
        _, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        # Yield each frame as part of the multipart response
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

    cap.release()

@app.route('/teacher/login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        # Manual username/password login
        username = request.form['username']
        password = request.form['password']

        teacher = teachers.find_one({"login_id": username, "password": password})
        if teacher:
            session['teacher_name'] = teacher['name']
            session['teacher_id'] = str(teacher['_id'])
            flash(f"Welcome {teacher['name']}!", "success")
            return redirect(url_for('teacher_dashboard'))
        else:
            flash("Invalid credentials", "error")
            return render_template('teacher_login.html')

    # Only proceed with face recognition on GET request
    cap = cv2.VideoCapture(0)
    warmup_start = time.time()
    recognition_start = None

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        cv2.imshow("Face Recognition Login", frame)
        cv2.waitKey(1)

        current_time = time.time()

        if recognition_start is None and current_time - warmup_start >= 5:
            recognition_start = current_time
            print("Starting face recognition...")

        if recognition_start:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            if face_encodings:
                encoding = face_encodings[0]
                teacher = find_teacher_by_face_encoding(encoding)

                if teacher:
                    session['teacher_name'] = teacher['name']
                    session['teacher_id'] = str(teacher['_id'])
                    cap.release()
                    cv2.destroyAllWindows()
                    flash(f"Welcome {teacher['name']} (Face Recognized)!", "success")
                    return redirect(url_for('teacher_dashboard'))

        # After 20 seconds, fail and open manual login
        if current_time - warmup_start > 20:
            cap.release()
            cv2.destroyAllWindows()
            flash("Face not recognized. Please log in manually.", "error")
            return render_template('teacher_login.html')




def find_teacher_by_face_encoding(encoding):
    # Retrieve all teachers from the database
    teachers_list = teachers.find()

    for teacher in teachers_list:
        stored_encoding = np.array(teacher['face_encoding'])
        # Compare the encodings using face_recognition
        matches = face_recognition.compare_faces([stored_encoding], encoding)
        
        if matches[0]:
            return teacher

    return None

@app.route('/teacher/capture_video_feed')
def capture_video_feed():
    """Route to stream the webcam feed to the frontend."""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


# Teacher Dashboard (after login)
@app.route('/teacher/dashboard')
def teacher_dashboard():
    if 'teacher_name' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('teacher_login'))
    
    return render_template('teacher_dashboard.html', name=session['teacher_name'])


# Take Attendance
@app.route('/teacher/take-attendance', methods=['GET', 'POST'])
def take_attendance():
    if 'teacher_name' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('teacher_login'))

    teacher_id = session['teacher_id']
    teacher = teachers.find_one({"_id": ObjectId(teacher_id)})

    if request.method == 'POST':
        class_name = request.form['class_name']
        subject_name = request.form['subject_name']

        # Get students only from selected class
        students_in_class = list(students.find({"Year": f"Year {class_name}"}))

        # Extract encodings
        known_encodings = [np.array(student['face_encoding']) for student in students_in_class]
        student_ids = [student['student_id'] for student in students_in_class]

        # Create a unique session ID for this session
        session_id = f"session_{str(int(time.time()))}"

        # Create a folder for storing attendance images
        folder_name = f"attendance_pics/{class_name}_{subject_name}_{session_id}"
        os.makedirs(folder_name, exist_ok=True)

        # Initialize webcam
        cap = cv2.VideoCapture(0)
        recognized_ids = []

        # Photo capture setup
        pic_interval = 5  # seconds
        total_pics = 3
        last_pic_time = time.time()
        pics_taken = 0

        start_time = time.time()
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            for face_encoding in face_encodings:
                matches = face_recognition.compare_faces(known_encodings, face_encoding)
                if True in matches:
                    match_index = matches.index(True)
                    student_id = student_ids[match_index]
                    if student_id not in recognized_ids:
                        recognized_ids.append(student_id)

            # Capture photo every 5 seconds
            current_time = time.time()
            if current_time - last_pic_time >= pic_interval and pics_taken < total_pics:
                image_path = os.path.join(folder_name, f"pic_{pics_taken+1}.jpg")
                cv2.imwrite(image_path, frame)
                print(f"[INFO] Saved image: {image_path}")
                last_pic_time = current_time
                pics_taken += 1

            if current_time - start_time > 15:  # 15 seconds for attendance
                break

            cv2.imshow("Attendance - Show your face", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

        # Build attendance list
        attendance = []
        for student in students_in_class:
            attendance.append({
                "student_id": student['student_id'],
                "present": student['student_id'] in recognized_ids,
                "class": class_name,
                "subject": subject_name
            })

        # Create or update the class_sessions record
        class_session = {
            "teacher_id": teacher_id,
            "teacher_name": teacher['name'],
            "class": class_name,
            "subject": subject_name,
            "sessions": [
                {
                    "session_id": session_id,
                    "timestamp": datetime.datetime.now()
                }
            ]
        }

        # Check if the class session already exists in the class_sessions database
        existing_class_session = class_sessions.find_one({
            "teacher_id": teacher_id,
            "class": class_name,
            "subject": subject_name
        })

        if existing_class_session:
            # Append session to existing
            class_sessions.update_one(
                {"teacher_id": teacher_id, "class": class_name, "subject": subject_name},
                {"$push": {"sessions": {"session_id": session_id, "timestamp": datetime.datetime.now()}}}
            )
        else:
            # Insert new session
            class_sessions.insert_one(class_session)

        # Store attendance
        attendance_record = {
            "session_id": session_id,
            "teacher_id": teacher_id,
            "class": class_name,
            "subject": subject_name,
            "attendance": attendance
        }

        attendance_db.insert_one(attendance_record)

        flash("Attendance marked successfully with classroom photos!", "success")
        return redirect(url_for('teacher_dashboard'))


    # For GET request, show dropdowns
    classes = teacher.get("classes", [])
    subjects = teacher.get("subjects", [])

    return render_template('take_attendance.html', classes=classes, subjects=subjects)

# # Generate Report
# @app.route('/teacher/generate-report', methods=['GET', 'POST'])
# def generate_report():
#     if 'teacher_name' not in session:
#         flash("Please log in first.", "error")
#         return redirect(url_for('teacher_login'))

#     teacher_id = session['teacher_id']
#     teacher = teachers.find_one({"_id": ObjectId(teacher_id)})

#     if request.method == 'POST':
#         class_name = request.form['class_name']
#         subject_name = request.form['subject_name']

#         # Get attendance data for the selected class and subject
#         attendance_data = attendance_db.find_one(
#             {"teacher_id": teacher_id, "class": class_name, "subject": subject_name}
#         )

#         if not attendance_data:
#             flash(f"No attendance data found for {class_name} - {subject_name}.", "error")
#             return redirect(url_for('teacher_dashboard'))

#         # Generate the report
#         report = []
#         for record in attendance_data['attendance_data']:
#             student = students.find_one({"student_id": record['student_id']})
#             report.append({
#                 "student_name": student['name'],
#                 "present": record['present']
#             })
        
#         # Export report as CSV
#         report_filename = f"attendance_report_{class_name}_{subject_name}.csv"
#         with open(report_filename, 'w', newline='') as file:
#             writer = csv.DictWriter(file, fieldnames=["student_name", "present"])
#             writer.writeheader()
#             writer.writerows(report)
        
#         flash(f"Report generated successfully! Download at {report_filename}", "success")
#         return redirect(url_for('teacher_dashboard'))

#     return render_template('generate_report.html')

# @app.route('/teacher/generate-report', methods=['GET', 'POST'])
# def generate_report():
#     if 'teacher_name' not in session:
#         flash("Please log in first.", "error")
#         return redirect(url_for('teacher_login'))

#     teacher_id = session['teacher_id']
#     teacher = teachers.find_one({"_id": ObjectId(teacher_id)})

#     if request.method == 'POST':
#         class_name = request.form['class_name']
#         subject_name = request.form['subject_name']
#         exam_type = request.form['exam_type']

#         # Define eligibility thresholds
#         thresholds = {
#             "IA1": 65,
#             "IA2": 75,
#             "IA3": 85,
#             "SEE": 75
#         }

#         # Fetch students in selected class
#         students_in_class = list(students.find({"Year": class_name}))

#         # Fetch sessions for selected class & subject
#         sessions = class_sessions.find_one({
#             "teacher_id": teacher_id,
#             "class": class_name,
#             "subject": subject_name
#         })

#         if not sessions or not sessions.get("sessions"):
#             flash("No class sessions found.", "error")
#             return redirect(url_for('teacher_dashboard'))

#         session_list = sessions['sessions']
#         session_ids = [s['session_id'] for s in session_list]

#         # Build student attendance map
#         student_attendance = {s['student_id']: [] for s in students_in_class}

#         # Loop through all relevant session records
#         for session_id in session_ids:
#             record = attendance_db.find_one({
#                 "session_id": session_id,
#                 "class": class_name,
#                 "subject": subject_name
#             })

#             if record:
#                 for entry in record['attendance']:
#                     student_attendance.setdefault(entry['student_id'], []).append(entry['present'])


#         # Generate CSV
#         filename = f"report_{class_name}_{subject_name}_{exam_type}.csv"
#         with open(filename, 'w', newline='') as file:
#             writer = csv.writer(file)
#             # Header row
#             header = ["Student Name"]
#             for i, sess in enumerate(session_list):
#                 header.append(f"Class-{i+1} ({sess['timestamp'].strftime('%d-%m-%Y %H:%M')})")
#             header += ["% Attendance", "Eligible?"]
#             writer.writerow(header)

#             # Student rows
#             for student in students_in_class:
#                 sid = student['student_id']
#                 name = student['name']
#                 records = student_attendance.get(sid, [])
#                 total_sessions = len(session_list)
#                 present_count = records.count(True)
#                 percentage = round((present_count / total_sessions) * 100, 2) if total_sessions > 0 else 0
#                 eligibility = "Yes" if percentage >= thresholds[exam_type] else "No"
#                 row = [name] + ["Present" if p else "Absent" for p in records]
#                 row += [f"{percentage}%", eligibility]
#                 writer.writerow(row)

#         flash(f"Report generated: {filename}", "success")
#         return redirect(url_for('teacher_dashboard'))

#     classes = teacher.get("classes", [])
#     subjects = teacher.get("subjects", [])
#     exams = ["IA1", "IA2", "IA3", "SEE"]
#     return render_template("generate_report.html", classes=classes, subjects=subjects, exams=exams)


@app.route('/teacher/generate-report', methods=['GET', 'POST'])
def generate_report():
    if 'teacher_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('teacher_login'))

    teacher_id = session['teacher_id']
    teacher = teachers.find_one({"_id": ObjectId(teacher_id)})

    if request.method == 'POST':
        class_name = request.form['class_name']
        subject = request.form['subject_name']
        exam_type = request.form['exam_type']

        session_doc = class_sessions.find_one({
            "teacher_id": teacher_id,
            "class": class_name,
            "subject": subject
        })

        if not session_doc or not session_doc.get('sessions'):
            flash("No sessions found for the selected class and subject.", "error")
            return redirect(url_for('generate_report'))

        sessions_list = sorted(session_doc['sessions'], key=lambda x: x['timestamp'])
        session_ids = [s['session_id'] for s in sessions_list]

        attendance_records = list(attendance_db.find({
            "session_id": {"$in": session_ids},
            "class": class_name,
            "subject": subject
        }))

        students_in_class = list(students.find({"Year": "Year " + class_name}))
        student_names = {s['student_id']: s['name'] for s in students_in_class}
        student_attendance = defaultdict(list)

        for student_id in student_names.keys():
            student_attendance[student_id] = []

        for record in attendance_records:
            attendance_map = {entry['student_id']: entry['present'] for entry in record['attendance']}
            for student_id in student_names.keys():
                student_attendance[student_id].append(attendance_map.get(student_id, False))

        eligibility_criteria = {
            'IA1': 65,
            'IA2': 75,
            'IA3': 85,
            'SEE': 75
        }

        report_rows = []
        headers = ['Student Name'] + [f"Class-{i+1} ({sessions_list[i]['timestamp'].strftime('%Y-%m-%d %H:%M')})" for i in range(len(sessions_list))] + ['Attendance %', 'Eligible']

        report_data = []
        for student_id, presence_list in student_attendance.items():
            name = student_names.get(student_id, "Unknown")
            total_classes = len(presence_list)
            present_count = sum(presence_list)
            percentage = round((present_count / total_classes) * 100, 2) if total_classes else 0
            eligible = "Yes" if percentage >= eligibility_criteria.get(exam_type, 75) else "No"

            row = [name] + ['Present' if p else 'Absent' for p in presence_list] + [percentage, eligible]
            report_rows.append(row)

            report_data.append({
                "student_id": student_id,
                "name": name,
                "attendances": presence_list,
                "percentage": percentage,
                "eligible": eligible
            })

        df = pd.DataFrame(report_rows, columns=headers)

        reports_dir = 'reports'
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)

        filename = f"{class_name}_{subject}_report.xlsx"
        filepath = os.path.join(reports_dir, filename)
        df.to_excel(filepath, index=False)

        flash(f"Report generated and saved as {filename} in reports folder.", "success")

        session_dates = [s['timestamp'].strftime('%Y-%m-%d %H:%M') for s in sessions_list]

        return render_template('report.html', report_data=report_data, session_dates=session_dates, subject=subject, class_name=class_name, exam_type=exam_type)

    classes = teacher.get("classes", [])
    subjects = teacher.get("subjects", [])

    return render_template('generate_report.html', classes=classes, subjects=subjects)



if __name__ == '__main__':
    # app.run(port=5001, debug=True)
    app.run(host='0.0.0.0', port=5001, debug=True)
