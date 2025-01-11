from flask import Flask, jsonify, request
from flask_cors import CORS
import yaml
import os
import mysql.connector as M
from datetime import datetime, timedelta
from imap_tools import MailBox, AND
from mail_bifurcation import GetPredictionByModel

app = Flask(__name__)
CORS(app,origins=["http://localhost"])

# Database connection
conn = M.connect(host='localhost', username='root', password='anu.adi@2005', database='mail_data')
curr = conn.cursor()
conn.commit()

@app.route('/', methods=['GET'])
def fetch_emails():
    now = datetime.now()
    delta = timedelta(minutes=2000)

    start_time = now - delta
    end_time = now

    start_time_date = start_time.date()
    end_time_date = end_time.date()

    with open("credential.yml") as file:
        content = file.read()

    cred = yaml.load(content, Loader=yaml.FullLoader)
    my_mail_id, password = cred["user"], cred["pass"]
    login_platform = "imap.gmail.com"

    mailBox = MailBox(login_platform).login(my_mail_id, password)

    emails = []
    attachment_dir = "attachments"
    if not os.path.exists(attachment_dir):
        os.makedirs(attachment_dir)

    extension_tags = [".jpeg", ".png", ".py", ".php", ".txt", ".html", ".pdf",".h5"]
    for i, msg in enumerate(mailBox.fetch(criteria=AND(date_gte=start_time_date, date_lt=end_time_date)), start=1):
        email_info = {
            "id": i,
            "Sender_id": msg.from_,
            "Reciever_id": msg.to,
            "subject": msg.subject,
            "date": msg.date_str,
            "body": msg.text,
            "attachments": []
        }

        for att in msg.attachments:
            attachment_filename = att.filename
            attachment_extension = os.path.splitext(attachment_filename)[1].lower()
            
            if attachment_extension in extension_tags:
                attachment_dir1 = os.path.join(attachment_dir, attachment_extension[1:])
            else:
                attachment_dir1 = attachment_dir
            
            if not os.path.exists(attachment_dir1):
                os.makedirs(attachment_dir1)
            
            file_path = os.path.join(attachment_dir1, attachment_filename)
            if not os.path.exists(file_path):
                with open(file_path, 'wb') as f:
                    f.write(att.payload)
                email_info["attachments"].append(file_path)
        emails.append(email_info)

    query1 = """CREATE TABLE IF NOT EXISTS mails (
      Id INT AUTO_INCREMENT PRIMARY KEY,
      sender_id VARCHAR(50),
      receiver_id VARCHAR(50), 
      type VARCHAR(25),
      flag INT,
      attachment VARCHAR(100),
      mail_time VARCHAR(100),
      storing_time DATETIME
    )"""
    curr.execute(query1)
    conn.commit()

    for email in emails:
        time = datetime.now()
        mail_text1 = f"{email['subject']} - {email['body']}"
        mail_text = mail_text1.replace('\n', ' ')
        type_of_mail = GetPredictionByModel(mail_text)
        query = """ INSERT INTO mails (
                sender_id, receiver_id, type,flag, attachment, mail_time, storing_time
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        
        flag = 1 if len(email["attachments"]) > 0 else 0
        
        val = (email["Sender_id"], email["Reciever_id"][0], type_of_mail, flag, ','.join(email["attachments"]), email["date"], time)
        curr.execute(query, val)
        conn.commit()
        delete_query = ''' DELETE t1 FROM mails t1
                        INNER JOIN mails t2
                        WHERE 
                        t1.Id > t2.Id AND 
                        t1.sender_id = t2.sender_id AND 
                        t1.receiver_id = t2.receiver_id AND 
                        t1.mail_time = t2.mail_time;
        '''
        curr.execute(delete_query)
        conn.commit()
        
    mailBox.logout()
    return jsonify({"message": "Emails fetched and saved successfully"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port = 4000 ,debug=True)
