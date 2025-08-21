from flask import Flask, render_template, request, redirect, session, url_for, flash
from pymongo import MongoClient

app = Flask(__name__)
app.secret_key = 'secret123'
client = MongoClient("mongodb://localhost:27017/")
db = client["face_db"]

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form['student_id']
        password = request.form['password']
        student = db.students.find_one({'student_id': student_id, 'password': password})
        if student:
            session['student_id'] = student_id
            session['class'] = student['Year']  # Fix: Use 'Year' field as class
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    student = db.students.find_one({'student_id': session['student_id']})
    return render_template('dashboard.html', name=student['name'])

@app.route('/report', methods=['GET', 'POST'])
def attendance_report():
    if 'student_id' not in session:
        return redirect(url_for('login'))

    student_id = session['student_id']
    student_class = session['class']  # e.g., "Year 3"
    mapped_class = student_class.split(" ")[1]  # Extract numeric part: "3"
    report_data = []
    session_dates = []
    selected_subject = exam_type = None

    # Retrieve subjects for the student's class
    subjects = db.class_sessions.distinct('subject', {'class': mapped_class})

    if request.method == 'POST':
        selected_subject = request.form['subject_name']
        exam_type = request.form['exam_type']

        # Fetch sessions for the selected class and subject
        sessions_doc = db.class_sessions.find_one({
            'class': mapped_class,
            'subject': selected_subject
        })

        session_ids = []
        if sessions_doc:
            session_ids = [s['session_id'] for s in sessions_doc['sessions']]
            session_dates = [s['timestamp'].strftime('%Y-%m-%d') for s in sessions_doc['sessions']]

        # Calculate attendance for each session
        attendances = []
        for sid in session_ids:
            att = db.attendance.find_one({
                'session_id': sid,
                'class': mapped_class,
                'subject': selected_subject
            })
            if att:
                present = any(s['student_id'] == student_id and s['present'] for s in att['attendance'])
                attendances.append(present)

        # Compute attendance percentage and eligibility
        percentage = round((sum(attendances) / len(attendances)) * 100, 2) if attendances else 0
        required = {'IA1': 65, 'IA2': 75, 'IA3': 85, 'SEE': 75}[exam_type]
        eligibility = "Eligible" if percentage >= required else "Not Eligible"

        report_data.append({
            'attendances': attendances,
            'percentage': percentage,
            'eligible': eligibility
        })

    return render_template('attendance_report.html',
                           session_dates=session_dates,
                           report_data=report_data,
                           selected_subject=selected_subject,
                           exam_type=exam_type,
                           subjects=subjects)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    # app.run(port=5002, debug=True)
    app.run(host='0.0.0.0', port=5002, debug=True)
