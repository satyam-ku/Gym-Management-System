# ==============================================================================
# SMART GYM MANAGEMENT SYSTEM - FINAL & COMPLETE BACKEND (app.py)
# DSA Project
# ==============================================================================

import os
import json
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from sqlalchemy import desc, func
from collections import deque

# ----------------- App Initialization & Configuration -----------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'the_ultimate_secret_key_for_dsa_project_v12_final'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'gym.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.permanent_session_lifetime = datetime.timedelta(days=7)

# ----------------- Extensions & Custom Filters -----------------
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# ----------------- DATABASE MODELS -----------------
trainer_client_association = db.Table('trainer_client',
    db.Column('trainer_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('client_id', db.Integer, db.ForeignKey('users.id'), primary_key=True)
)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    goal = db.Column(db.String(100))
    # Relationships
    weight_logs = db.relationship('WeightLog', backref='user', lazy=True, cascade="all, delete-orphan")
    bookings = db.relationship('Booking', backref='member', lazy='dynamic', cascade="all, delete-orphan")
    waitlist_entries = db.relationship('Waitlist', backref='member', lazy='dynamic', cascade="all, delete-orphan")
    workout_plans = db.relationship('WorkoutPlan', backref='member', lazy='dynamic', cascade="all, delete-orphan")
    clients = db.relationship('User', secondary=trainer_client_association,
                              primaryjoin=(trainer_client_association.c.trainer_id == id),
                              secondaryjoin=(trainer_client_association.c.client_id == id),
                              backref=db.backref('assigned_trainer', lazy='dynamic'), lazy='dynamic')

class Class(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    day = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(20), nullable=False)
    duration = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=3)
    bookings = db.relationship('Booking', backref='class_info', lazy='dynamic', cascade="all, delete-orphan")
    waitlist_entries = db.relationship('Waitlist', backref='class_info', lazy='dynamic', cascade="all, delete-orphan")

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    status = db.Column(db.String(20), default='BOOKED', nullable=False)

class Waitlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)

class WorkoutPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    trainer_name = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    assigned_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class WeightLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.date.today)
    weight_lb = db.Column(db.Float, nullable=False)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# ----------------- HELPER FUNCTIONS -----------------
def get_current_user():
    return User.query.get(session.get('user_id')) if 'user_id' in session else None

def time_ago(date):
    if not date: return "never"
    diff = datetime.datetime.utcnow() - date
    if diff.days > 0: return f"{diff.days}d ago"
    if diff.seconds > 3600: return f"{diff.seconds // 3600}h ago"
    return f"{diff.seconds // 60}m ago" if diff.seconds > 60 else "just now"

def log_activity(user_name, message):
    db.session.add(ActivityLog(user_name=user_name, message=message))

# ----------------- CORE & AUTHENTICATION ROUTES -----------------
@app.route('/')
def home():
    if 'user_id' in session: return redirect(url_for(f"{session.get('role', 'member')}_dashboard"))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    user = User.query.filter_by(email=data.get('email')).first()
    if user and bcrypt.check_password_hash(user.password, data.get('password')) and user.role == data.get('role'):
        session.clear(); session['user_id'] = user.id; session['name'] = user.name; session['role'] = user.role
        return jsonify({'success': True, 'redirect_url': url_for(f"{user.role}_dashboard")})
    return jsonify({'success': False, 'message': 'Invalid credentials or role mismatch.'})

@app.route('/signup', methods=['POST'])
def signup():
    data = request.form
    if User.query.filter_by(email=data.get('email')).first(): return jsonify({'success': False, 'message': 'This email is already registered.'})
    hashed_password = bcrypt.generate_password_hash(data.get('password')).decode('utf-8')
    new_user = User(name=data.get('name'), email=data.get('email'), password=hashed_password, role=data.get('role'))
    db.session.add(new_user)
    if new_user.role == 'member':
        trainer = User.query.filter_by(role='trainer').first()
        if trainer: trainer.clients.append(new_user)
    db.session.commit(); log_activity(new_user.name, f"registered as a new {new_user.role}."); db.session.commit()
    return jsonify({'success': True, 'message': 'Account created! Please log in.'})

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('home'))

# ----------------- DASHBOARD & FUNCTIONAL ROUTES -----------------
@app.route('/member_dashboard')
def member_dashboard():
    user = get_current_user()
    if not user or user.role != 'member': return redirect(url_for('home'))
    attended_dates = {b.booking_date.date().isoformat() for b in user.bookings.filter_by(status='ATTENDED').all()}
    return render_template('member_dashboard.html', user=user, attended_dates=list(attended_dates))

@app.route('/trainer_dashboard')
def trainer_dashboard():
    trainer = get_current_user()
    if not trainer or trainer.role != 'trainer':
        return redirect(url_for('home'))

    # Fetch clients assigned to this trainer
    clients = trainer.clients.order_by(User.name).all()
    client_ids = [c.id for c in clients]

    # Calculate stats
    upcoming_classes_count = Booking.query.filter(
        Booking.user_id.in_(client_ids),
        func.date(Booking.booking_date) >= datetime.date.today()
    ).distinct(Booking.class_id).count()

    stats = {
        'active_clients': len(clients),
        'upcoming_classes': upcoming_classes_count,
        'training_plans': WorkoutPlan.query.filter(WorkoutPlan.member_id.in_(client_ids)).count()
    }

    
    client_names = [c.name for c in clients]
    activities_raw = ActivityLog.query.filter(ActivityLog.user_name.in_(client_names)).order_by(desc(ActivityLog.timestamp)).limit(5).all()
    activities = [{'user': log.user_name, 'action': log.message, 'time': time_ago(log.timestamp)} for log in activities_raw]

    # Add last active time to each client object
    for client in clients:
        last_booking = client.bookings.order_by(desc(Booking.booking_date)).first()
        client.last_active = time_ago(last_booking.booking_date) if last_booking else "No activity"

    return render_template(
        'trainer_dashboard.html',
        trainer=trainer,
        stats=stats,
        clients=clients,
        activities=activities
    )

@app.route('/admin_dashboard')
def admin_dashboard():
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('home'))

    stats = {
        'total_members': User.query.filter_by(role='member').count(),
        'active_classes': Class.query.count(),
        'total_revenue': 86600
    }
    logs_raw = ActivityLog.query.order_by(desc(ActivityLog.timestamp)).limit(5).all()
    activity_logs = [{'user': log.user_name, 'action': log.message, 'time': time_ago(log.timestamp)} for log in logs_raw]
    users_list = User.query.order_by(User.role, User.name).all()
    revenue_data = {'Jan': 5000, 'Feb': 5500, 'Mar': 9000, 'Apr': 15000, 'May': 22000, 'Jun': 25100}
    classes = Class.query.all()

    return render_template(
        'admin_dashboard.html',
        admin=user,
        stats=stats,
        activities=activity_logs,
        users_list=users_list,
        revenue_data=revenue_data,
        classes=classes
    )

@app.route('/admin/view_user/<int:user_id>')
def admin_view_user(user_id):
    admin = get_current_user()
    if not admin or admin.role != 'admin':
        return "Unauthorized", 403
    user_to_view = User.query.get_or_404(user_id)
    weight_history = sorted(user_to_view.weight_logs, key=lambda x: x.date, reverse=True)
    attended_dates = {b.booking_date.date().isoformat() for b in user_to_view.bookings.filter_by(status='ATTENDED').all()}
    all_bookings = user_to_view.bookings.join(Class).order_by(desc(Booking.booking_date)).all()
    workout_plans = user_to_view.workout_plans.order_by(desc(WorkoutPlan.assigned_date)).all()
    return render_template('admin_view_user.html', client=user_to_view, weight_history=weight_history, attended_dates=list(attended_dates), all_bookings=all_bookings, workout_plans=workout_plans)

@app.route('/view_client/<int:client_id>')
def view_client(client_id):
    trainer = get_current_user()
    client = User.query.get_or_404(client_id)
    if not trainer or trainer.role != 'trainer' or client not in trainer.clients:
        return "Unauthorized", 403
    weight_history = sorted(client.weight_logs, key=lambda x: x.date, reverse=True)
    attended_dates = {b.booking_date.date().isoformat() for b in client.bookings.filter_by(status='ATTENDED').all()}
    todays_bookings = Booking.query.filter(Booking.user_id == client_id, func.date(Booking.booking_date) == datetime.date.today()).all()
    return render_template('view_client_details.html', client=client, weight_history=weight_history, attended_dates=list(attended_dates), todays_bookings=todays_bookings)

@app.route('/workout')
def workout():
    return render_template('workout.html')

@app.route('/class_booking')
def class_booking():
    user = get_current_user()
    if not user: return redirect(url_for('home'))
    return render_template('class_booking.html', classes=Class.query.all())

# ----------------- API ROUTES (FOR JS) -----------------
@app.route('/api/remove_user/<int:user_id>', methods=['POST'])
def remove_user(user_id):
    admin = get_current_user()
    if not admin or admin.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access.'}), 403
    if admin.id == user_id:
        return jsonify({'success': False, 'message': 'You cannot remove your own account.'}), 400
    user_to_delete = User.query.get(user_id)
    if not user_to_delete:
        return jsonify({'success': False, 'message': 'User not found.'}), 404
    try:
        user_name = user_to_delete.name
        db.session.delete(user_to_delete)
        log_activity(admin.name, f"removed user '{user_name}' (ID: {user_id}).")
        db.session.commit()
        return jsonify({'success': True, 'message': f"User '{user_name}' has been successfully removed."})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An error occurred while removing the user.'}), 500

@app.route('/api/book_class', methods=['POST'])
def api_book_class():
    user = get_current_user()
    if not user: return jsonify({'success': False, 'message': 'Not logged in'}), 401
    class_id = request.json.get('class_id')
    if Booking.query.filter_by(user_id=user.id, class_id=class_id).first():
        return jsonify({'success': False, 'message': 'Already booked'})
    target_class = Class.query.get(class_id)
    if target_class.bookings.count() >= target_class.capacity:
        db.session.add(Waitlist(user_id=user.id, class_id=class_id))
        log_activity(user.name, f"joined waitlist for '{target_class.name}'.")
        db.session.commit()
        return jsonify({'success': True, 'message': 'Class is full. You have been added to the waitlist.'})
    db.session.add(Booking(user_id=user.id, class_id=class_id)); log_activity(user.name, f"booked '{target_class.name}'."); db.session.commit()
    return jsonify({'success': True, 'message': 'Booked Successfully!'})

@app.route('/api/cancel_booking/<int:booking_id>', methods=['POST'])
def api_cancel_booking(booking_id):
    user = get_current_user()
    if not user: return jsonify({'success': False, 'message': 'Not logged in'}), 401
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != user.id and user.role != 'admin': return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    class_id = booking.class_id; class_name = booking.class_info.name
    db.session.delete(booking); log_activity(booking.member.name, f"cancelled booking for '{class_name}'.")
    first_waitlisted = Waitlist.query.filter_by(class_id=class_id).order_by(Waitlist.timestamp.asc()).first()
    if first_waitlisted:
        db.session.add(Booking(user_id=first_waitlisted.user_id, class_id=class_id))
        log_activity(first_waitlisted.member.name, f"auto-booked for '{class_name}' from waitlist.")
        db.session.delete(first_waitlisted)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Booking cancelled successfully.'})

@app.route('/api/assign_plan', methods=['POST'])
def api_assign_plan():
    trainer = get_current_user()
    if not trainer or trainer.role != 'trainer': return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    data = request.json
    new_plan = WorkoutPlan(member_id=data['member_id'], trainer_name=trainer.name, title=data['title'], description=data['description'])
    db.session.add(new_plan); log_activity(trainer.name, f"assigned plan '{data['title']}' to member ID {data['member_id']}."); db.session.commit()
    return jsonify({'success': True, 'message': 'Plan assigned successfully!'})

@app.route('/api/mark_attendance', methods=['POST'])
def api_mark_attendance():
    trainer = get_current_user()
    if not trainer or trainer.role != 'trainer': return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    booking_id = request.form.get('booking_id'); status = request.form.get('status')
    booking = Booking.query.get(booking_id)
    if not booking or status not in ['ATTENDED', 'MISSED']: return jsonify({'success': False, 'message': 'Invalid data'}), 400
    booking.status = status; log_activity(trainer.name, f"marked {booking.member.name} as {status.lower()} for '{booking.class_info.name}'"); db.session.commit()
    return jsonify({'success': True, 'message': 'Attendance updated'})


@app.cli.command("init-db")
def init_db_command():
    with app.app_context():
        db.drop_all(); db.create_all()
        admin = User(name='Admin User', email='admin@gym.com', password=bcrypt.generate_password_hash('admin').decode('utf-8'), role='admin')
        trainer = User(name='Sara Holmes', email='sara@example.com', password=bcrypt.generate_password_hash('trainer').decode('utf-8'), role='trainer')
        db.session.add_all([admin, trainer])
        members_data = [{'name': 'John Doe', 'email': 'john@example.com', 'goal': 'Weight Loss'},{'name': 'Mara Pinto', 'email': 'mara@example.com', 'goal': 'General Fitness'},{'name': 'Raj Kumar', 'email': 'raj@example.com', 'goal': 'Weight Loss'},{'name': 'Anita Singh', 'email': 'anita@example.com', 'goal': 'Bodybuilding'}]
        for m in members_data:
            member = User(name=m['name'], email=m['email'], password=bcrypt.generate_password_hash('member').decode('utf-8'), role='member', goal=m['goal'])
            trainer.clients.append(member); db.session.add(member)
        classes_data = [
            {'n':'Yoga','d':'Find balance & peace of mind in this gentle yoga.','day':'Mon','t':'6:00 am','dur':'60 min','img':'https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?auto=format&fit=crop&w=400'},
            {'n':'Spinning','d':'Join our high-energy spinning class to improve your cardiovascular fitness.','day':'Tue','t':'7:00 am','dur':'45 min','img':'https://images.unsplash.com/photo-1599447462855-40c94868978a?auto=format&fit=crop&w=400'},
            {'n':'Kickboxing','d':'Engage in an intense workout that combines martial arts.','day':'Wed','t':'7:00 am','dur':'50 min','img':'https://images.unsplash.com/photo-1517438322306-4a8134a6424a?auto=format&fit=crop&w=400'},
            {'n':'Pilates','d':'Strengthen your core and improve flexibility with our Pilates sessions.','day':'Thu','t':'9:00 am','dur':'50 min','img':'https://images.unsplash.com/photo-1598422856984-a28d5a1458e6?auto=format&fit=crop&w=400'},
            {'n':'Zumba','d':'Dance to great music, with great people, and burn a ton of calories.','day':'Fri','t':'6:00 pm','dur':'55 min','img':'https://images.unsplash.com/photo-1593121924236-4695180a61e3?auto=format&fit=crop&w=400'},
            {'n':'HIIT','d':'High-Intensity Interval Training for maximum calorie burn in a short time.','day':'Sat','t':'8:00 am','dur':'30 min','img':'https://images.unsplash.com/photo-1517836357463-d25dfeac3438?auto=format&fit=crop&w=400'},
        ]
        for c in classes_data: db.session.add(Class(name=c['n'], description=c['d'], day=c['day'], time=c['t'], duration=c['dur'], image_url=c['img']))
        db.session.commit()
        john = User.query.filter_by(email='john@example.com').first()
        mara = User.query.filter_by(email='mara@example.com').first()
        yoga_class = Class.query.filter_by(name='Yoga').first()
        spinning_class = Class.query.filter_by(name='Spinning').first()
        if john and yoga_class:
            db.session.add(Booking(member=john, class_info=yoga_class, status='ATTENDED', booking_date=datetime.datetime.utcnow() - datetime.timedelta(days=2)))
            db.session.add(WeightLog(user_id=john.id, date=datetime.date.today() - datetime.timedelta(days=10), weight_lb=182))
            db.session.add(WeightLog(user_id=john.id, date=datetime.date.today() - datetime.timedelta(days=5), weight_lb=178))
        if mara and spinning_class:
            db.session.add(Booking(member=mara, class_info=spinning_class, booking_date=datetime.datetime.today()))
            db.session.add(WorkoutPlan(member_id=mara.id, trainer_name="Sara Holmes", title="Beginner Cardio Plan", description="Start with 20 mins of treadmill, 3 times a week."))
        log_activity('John Doe', 'logged a new weight'); log_activity('Mara Pinto', 'booked Spinning')
        db.session.commit()
        print("Database initialized successfully with sample data.")

# ----------------- Main Execution -----------------
if __name__ == '__main__':
    app.run(debug=True, port=5001)