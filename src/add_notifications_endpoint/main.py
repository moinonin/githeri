from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import smtplib
from email.mime.text import MIMEText
import requests

app = FastAPI()

class NotificationRequest(BaseModel):
    email: str
    message: str
    push_token: str

@app.post("/notifications")
def send_notifications(request: NotificationRequest):
    try:
        # Send email
        msg = MIMEText(request.message)
        msg['Subject'] = 'Notification'
        msg['From'] = 'sender@example.com'
        msg['To'] = request.email
        with smtplib.SMTP('smtp.example.com', 587) as server:
            server.starttls()
            server.login('username', 'password')
            server.sendmail('sender@example.com', request.email, msg.as_string())

        # Send push notification
        payload = {
            "token": request.push_token,
            "message": request.message
        }
        response = requests.post('https://pushnotificationapi.com/send', json=payload)
        response.raise_for_status()

        return {'status': 'success'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))