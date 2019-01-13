#!usr/bin/env python
# -*-coding:Utf-8 *-

""" This module handles sending emails. It contains:
    - The function send_email which allows to send an email with
    one or more image as attachment and a plain text message with a
    timestamp

"""

# Standard Python libraries
import smtplib
import ssl
from os import path
from time import strftime, localtime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage


def send_email(project_conf, timestamp, list_image_path):
    """ Send an email with an image as attachment and its associated timestamp
    Arguments:
    - project_conf: Dictionary that must contain the following keys:
        - "email_address" -> email address used to send the email
        - "email_subject" -> Subject of the email to be sent
        - "email_list_to_alert" -> email addresses list on which the email
        must be sent
        - "smtp_server" -> the address of the smtp server used
    - timestamp: the timestamp associated to the image to be sent, in number
    of seconds since epoch
    - list_image_path: filepath list of images to be sent

    """
    # Create a message object instance and setup
    mime_msg = MIMEMultipart()
    mime_msg["From"] = project_conf["email_address"]
    if len(project_conf["email_list_to_alert"]) > 1:
        mime_msg["To"] = ", ".join(project_conf["email_list_to_alert"])
    else:
        mime_msg["To"] = project_conf["email_list_to_alert"][0]
    mime_msg["Subject"] = project_conf["email_subject"]

    # Set a plain text message
    timestamp = strftime("%A %d %B %Y %H:%M:%S", localtime(timestamp))
    text_msg = "PiCamera has detected motion"\
               "\nTimestamp: {}".format(timestamp)
    # Attach text to the mime_msg
    mime_msg.attach(MIMEText(text_msg, "plain"))

    for image_path in list_image_path:
        # Attach image to the mime_msg and add an attachment name
        with open(image_path, "rb") as image_raw:
            mime_img = MIMEImage(image_raw.read())
        mime_img.add_header('Content-Disposition',
                            'attachment;'
                            ' filename={}'.format(path.basename(image_path)))
        mime_msg.attach(mime_img)
    # Create SSL default context
    context = ssl.create_default_context()
    # Create an SMTP instance
    mail_server = smtplib.SMTP(project_conf["smtp_server"], 587)
    # Put SMTP connection in TLS mode
    mail_server.starttls(context=context)
    # Login
    mail_server.login(project_conf["email_address"],
                      project_conf["email_password"])
    # Send the email
    mail_server.sendmail(project_conf["email_address"],
                         project_conf["email_list_to_alert"],
                         mime_msg.as_string())
    # Quit SMTP session
    mail_server.quit()
