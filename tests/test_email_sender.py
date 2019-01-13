#!/usr/bin/env python3
# coding: utf-8

import unittest
import json
from os import path
import sys
from time import time, strftime, localtime, sleep
import imaplib
import email
import hashlib
import re

sys.path.append(path.dirname(path.dirname(path.realpath(__file__))))

from email_sender import send_email


class EmailSenderTester(unittest.TestCase):

    def setUp(self):
        self.PROJECT_CONF_FILE_NAME = "my_conf.json"
        self.IMAP_SERVER = "imap.gmail.com"
        self.IMAP_PORT = 993
        self.MAIL_CONTENT_TYPES = ["multipart/mixed", "text/plain",
                                   "image/jpeg"]
        with open(self.PROJECT_CONF_FILE_NAME, 'r') as project_conf_file:
            self.project_conf = json.load(project_conf_file)
        self.mail_server = imaplib.IMAP4_SSL(self.IMAP_SERVER, self.IMAP_PORT)
        self.mail_server.login(self.project_conf["email_address"],
                               self.project_conf["email_password"])

    def retrieve_email(self, folder_name):
            typ, folders = self.mail_server.list()
            pattern = ".*{}.*".format(folder_name)
            r = re.compile(pattern.encode())
            for folder in folders:
                if r.match(folder):
                    folder_name = folder
                    break
            pattern = r'"/" ".*"$'
            match = re.search(pattern.encode(), folder_name)
            folder_name = match.group(0)[4:]

            self.mail_server.select(folder_name)

            typ, msgnums = self.mail_server.search(None, 'SUBJECT "{}"'.format(
                                                   self.project_conf
                                                   ["email_subject"]))

            error_msg = "Email not found in {}".format(folder_name)
            self.assertTrue(len(msgnums[0]) > 0, error_msg)

            id_list = msgnums[0].split()
            test_email_id = id_list[-1]
            typ, data = self.mail_server.fetch(test_email_id, '(RFC822)')
            msg = email.message_from_bytes(data[0][1])
            return msg, test_email_id

    def core_test(self, timestamp, image_path_list):

        send_email(self.project_conf, timestamp, image_path_list)

        sleep(2)

        msg, test_email_id = self.retrieve_email("INBOX")
        im_num = 0
        for part in msg.walk():
            self.assertIn(part.get_content_type(), self.MAIL_CONTENT_TYPES,
                          "Unexpected message part")
            if part.get_content_type() == self.MAIL_CONTENT_TYPES[0]:
                receivers = ", ".join(self.project_conf["email_list_to_alert"])
                self.assertEqual(part["To"], receivers)
            elif part.get_content_type() == self.MAIL_CONTENT_TYPES[1]:
                formated_timestamp = strftime("%A %d %B %Y %H:%M:%S",
                                              localtime(timestamp))
                text_msg = "PiCamera has detected motion"\
                           "\r\nTimestamp: {}".format(formated_timestamp)
                self.assertEqual(part.get_payload(), text_msg)
            elif part.get_content_type() == self.MAIL_CONTENT_TYPES[2]:
                self.assertEqual(part.get_filename(),
                                 path.basename(image_path_list[im_num]))
                image_email = part.get_payload(decode=True)
                image_email_hash = hashlib.sha256(image_email).hexdigest()
                with open(image_path_list[im_num], "rb") as image_raw:
                    image = image_raw.read()
                image_hash = hashlib.sha256(image).hexdigest()
                self.assertEqual(image_email_hash, image_hash)
                im_num += 1

        self.mail_server.store(test_email_id, '+X-GM-LABELS', '\\Trash')
        self.mail_server.expunge()

        msg, test_email_id = self.retrieve_email("Trash")
        self.mail_server.store(test_email_id, '+FLAGS', '\\Deleted')

        self.mail_server.expunge()
        self.mail_server.close()
        self.mail_server.logout()

    def test_multi_img_and_multi_receivers(self):

        timestamp = time()

        self.project_conf["email_subject"] = "Test Security Alert"
        self.project_conf["email_list_to_alert"] = [self.project_conf
                                                    ["email_address"],
                                                    self.project_conf
                                                    ["email_address"]]

        image_path_list = ["tests/alert.jpg", "tests/pingouin.jpg"]
        image_path_list = [path.realpath(image_path) for image_path in
                           image_path_list]

        self.core_test(timestamp, image_path_list)

    def test_single_img_and_single_receivers(self):

        timestamp = time()

        self.project_conf["email_subject"] = "Test Security Alert"
        self.project_conf["email_list_to_alert"] = [self.project_conf
                                                    ["email_address"]]

        image_path_list = ["tests/alert.jpg"]
        image_path_list = [path.realpath(image_path) for image_path in
                           image_path_list]

        self.core_test(timestamp, image_path_list)


if __name__ == '__main__':
    unittest.main()
