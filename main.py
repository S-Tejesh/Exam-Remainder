import os
from flask import Flask, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
import pandas as pd
import smtplib
from twilio.rest import Client
from datetime import datetime, timedelta
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = 'bogus'

login_manager = LoginManager(app)
login_manager.login_view = 'login'
account_sid="your sid from twilio"
auth_token="your token from twilio"

@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response


# User model
class User(UserMixin):
    def __init__(self, username, password):
        self.id = 1  # A single user with ID 1
        self.username = username
        self.password = password


def load_user_from_excel(file_path):
    users_df = pd.read_excel(file_path)
    if not users_df.empty:
        row = users_df.iloc[0]  # Assuming there is only one row
        username = row['username']  # Assuming 'username' is a column in your Excel file
        password = row['password']  # Assuming 'password' is a column in your Excel file
        user = User(username, password)
        return user
    return None


# Load a single user from the Excel file
single_user = load_user_from_excel('dir_details.xlsx')


# User loader function
@login_manager.user_loader
def load_user(user_id):
    return single_user


def exam_function(file):
    if os.listdir('uploads/officer_file'):
        officer_files_path = os.path.join("uploads", "officer_file")
        file_path = os.path.join(officer_files_path, os.listdir(officer_files_path)[0])
        df = pd.read_excel(file)
        current_date = datetime.now().date()
        matching_rows = []
        for index, row in df.iterrows():
            if row['calculated_date'] == str(current_date):
                matching_row_dict = row.to_dict()
                matching_rows.append(matching_row_dict)
        msg_path = "new_data.csv"
        df2 = pd.read_excel(file_path)
        load_dotenv()
        my_email = os.environ.get("from_mail")
        app_password = os.environ.get("app_pass")
        for i in range(len(matching_rows)):
            email = df2[df2["officer"].isin(list(matching_rows[i]["officer"].split(",")))]['email']
            mobile = df2[df2["officer"].isin(list(matching_rows[i]["officer"].split(",")))]['phone']
            print(type(mobile))
            with open(msg_path) as f:
                contents = f.read()
            contents=contents.replace('[event]',matching_rows[i]["Event"])
            date_obj = datetime.strptime(matching_rows[i]["calculated_date"], "%Y-%m-%d")
            one_week_before = date_obj + timedelta(days=7)
            event_date = one_week_before.strftime('%Y-%m-%d')
            contents = contents.replace('[date]',event_date)
            print(contents)
            #for mobile alerts
            for num in mobile:
                print(num)
                client = Client(account_sid, auth_token)
                message = client.messages \
                    .create(
                    body=f"{contents}",
                    from_="your twilio number",  # this is twilio phone number
                    to=f"+91{int(num)}"  # actual number to receive sms
                )
                print(message.status)
            #for mail alerts
            for every in email:
                with smtplib.SMTP("smtp.gmail.com") as connection:
                    connection.starttls()
                    connection.login(user=my_email, password=app_password)
                    connection.sendmail(from_addr=my_email,
                                        to_addrs=every,
                                        msg=f"Subject:Hello\n\n{contents}")

def update_dates(t, fp):
    df = pd.read_excel(fp)
    date_format = "%d-%m-%Y"  # Format of the date string
    date_object = datetime.strptime(t, date_format)

    def calculate_date(row):
        operator, days = row['dates'][1], int(row['dates'][2:])
        if operator == '+':
            return str(date_object + timedelta(days=days - 7)).split(' ')[0]
        elif operator == '-':
            return str(date_object - timedelta(days=days + 7)).split(' ')[0]

    df['calculated_date'] = df.apply(calculate_date, axis=1)
    with pd.ExcelWriter(fp, engine='openpyxl', mode='a', if_sheet_exists='replace',
                        datetime_format='yyyy-mm-dd') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')


def allowed_file(filename):
    # Define allowed file extensions (e.g., '.xlsx')
    allowed_extensions = {'xlsx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


@app.route('/')
@login_required
def home():
    return render_template('home.html')


app.config['UPLOAD_FOLDER'] = 'uploads'  # Base upload directory

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


@app.route('/send-alerts', methods=['GET', 'POST'])
def alerting():
    page = request.form.get('button')
    directory_path = 'uploads/tsheet'
    msg=''
    if not os.listdir(directory_path):
        msg+='no tsheets available '
    if not os.listdir('uploads/officer_file'):
        msg+='no officer files available '
    else:
        msg='alerts have been sent'
    for filename in os.listdir(directory_path):
        file1 = os.path.join(directory_path, filename)
        if os.path.isfile(file1):
            df = pd.read_excel(file1)
            date_obj = datetime.strptime(df.iloc[-1, 3], '%Y-%m-%d')
            if date_obj < datetime.now():
                os.remove(file1)
            else:
                exam_function(file1)
    if page == '1':
        return redirect(url_for('login', info=msg))
    else:
        return redirect(url_for('home', info=msg))


@app.route('/upload', methods=['GET', 'POST'])
def upload_files():
    if request.method == 'POST':
        uploaded_file1 = request.files.get('officer_file')
        uploaded_file2 = request.files.get('tsheet')
        if not (uploaded_file1.filename or uploaded_file2.filename):
            return redirect(url_for('home', info='no file was uploaded'))
        if 'officer_file' in request.files:
            button1_files = request.files.getlist('officer_file')
            button1_directory = os.path.join(app.config['UPLOAD_FOLDER'], 'officer_file')
            if not os.path.exists(button1_directory):
                os.makedirs(button1_directory)
            for file in button1_files:
                if file.filename.endswith('.xlsx'):
                    file_list = os.listdir(button1_directory)
                    for f in file_list:
                        file_path1 = os.path.join(button1_directory, f)
                        os.remove(file_path1)
                    fp = os.path.join(button1_directory, file.filename)
                    file.save(fp)

        if 'tsheet' in request.files:
            button2_files = request.files.getlist('tsheet')
            button2_directory = os.path.join(app.config['UPLOAD_FOLDER'], 'tsheet')
            user_input = request.form.get('user_input')
            if not os.path.exists(button2_directory):
                os.makedirs(button2_directory)

            for file in button2_files:
                if file.filename.endswith('.xlsx'):
                    fp = os.path.join(button2_directory, file.filename)
                    file.save(fp)
                    update_dates(user_input, fp)
    return redirect(url_for('home', info='file uploaded successfully'))


@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        name1 = request.form['username']
        pwd = request.form['password']
        if name1 == single_user.username and pwd == single_user.password:
            login_user(single_user)
            return redirect(url_for('home'))
        elif name1 != single_user.username:
            return redirect(url_for('login', info='! invalid user'))
        else:
            return redirect(url_for('login', info='! invalid credentials'))
    return render_template('login.html')


@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        # Check if the old password is valid
        # Compare new_password and confirm_password

        # If validation passes, update the user's password in the database
        if old_password == single_user.password and new_password == confirm_password:
            df = pd.read_excel('dir_details.xlsx')
            df['password'] = new_password
            df.to_excel('dir_details.xlsx', index=False)
            single_user.password = new_password
            logout_user()
            return redirect(url_for('login', info='You have changed password successfully'))
        else:
            return redirect(url_for('change_password', info='enter password correctly'))

    return render_template('change_password.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login',info='you have successfully logged out'))


if __name__ == "__main__":
    app.run()
