#!/usr/bin/env python
# -*-coding:Utf-8 *-

""" This file is the main function of the security cam project.
Using the picamera, this program detects motion from a adaptative
background and sends an email to alert the owner.
For configuration, it relies on 1 JSON conf file named 'conf.json'
which must be in the same directory

It relies on 2 third party libraries:
    - cv2
    - picamera

It relies on 1 project module:
    - email_sender

"""

# Standard Python libraries
import json
from time import sleep, time, strftime, localtime
from os import path, mkdir
from sys import exit

# Third Party Libraries
import cv2
from picamera import PiCamera
from picamera.array import PiRGBArray

# Project Modules
from email_sender import send_email


# Constants
PROJECT_CONF_FILE_NAME = "conf.json"

# Global variables
motion_detected = False
email_sent_timestamp = 0
motion_counter = 0
project_conf = {}
average_background = None


print("Surveillance startup.")

# Check if the configuration file exists
print("Check if conf file exists: ", end="")
if path.exists(PROJECT_CONF_FILE_NAME):
    print("OK")
else:
    print("NO")
    print("Conf file {} does not exist".format(PROJECT_CONF_FILE_NAME))
    exit(0)

# Open the JSON configuration file and load it to the project_conf dictionary
print("Load {} configuration file.".format(PROJECT_CONF_FILE_NAME))
with open(PROJECT_CONF_FILE_NAME, 'r') as project_conf_file:
    try:
        project_conf = json.load(project_conf_file)
    except ValueError as error:
        print("Error: ", error)
        print("Failed to load JSON file: {}".format(PROJECT_CONF_FILE_NAME))
        exit(0)
    else:
        print("Configuration file {} loaded.".format(PROJECT_CONF_FILE_NAME))

# Create a PiCamera object instance with the resolution and framerate defined
# in the configuration file
print("Start camera.")
with PiCamera(resolution=tuple(project_conf["resolution"]),
              framerate=project_conf["fps"]) as camera:

    # Wait for the camera to warm up as recommended in the documentation
    print("Wait for camera warm up "
          "({}s).".format(project_conf["camera_warm_up_time"]))
    sleep(project_conf["camera_warm_up_time"])
    print("Camera is ready.")

    # Create a PiRGBArray object instance to work with numpy array
    camera_frame = PiRGBArray(camera,
                              size=tuple(project_conf["resolution"]))

    # Infinite Loop through frames captured by the PiCamera
    for frame in camera.capture_continuous(camera_frame, format="bgr",
                                           use_video_port=True):

        # Retrieve numpy array from PiRGBArray object instance
        frame_array = camera_frame.array
        # Get frame timestamp
        motion_frame_timestamp = time()

        # Image processing-----------------------------------------------------

        # Convert frame array from bgr format to gray
        frame_array_gray = cv2.cvtColor(frame_array, cv2.COLOR_BGR2GRAY)

        if project_conf["local_visualization"]:
            cv2.imshow("Gray Frame", frame_array_gray)

        # Apply Gaussian blur to reduce details and noise
        frame_array_gray = cv2.GaussianBlur(frame_array_gray,
                                            tuple(project_conf["blur_size"]),
                                            0)

        if project_conf["local_visualization"]:
            cv2.imshow("Blurred Gray Frame", frame_array_gray)

        # Take the first frame as average_background
        if average_background is None:
            # Make a copy of the gray frame array and convert it to
            # float array
            average_background = frame_array_gray.copy().astype("float")
            camera_frame.truncate()
            camera_frame.seek(0)
            continue

        # Update the average background
        average_background = cv2.accumulateWeighted(frame_array_gray.astype
                                                    ("float"),
                                                    average_background, 0.5)
        # Compute the absolute difference between the current frame and the
        # average background to detect motion
        frameDelta = cv2.absdiff(frame_array_gray,
                                 cv2.convertScaleAbs(average_background))

        if project_conf["local_visualization"]:
            cv2.imshow("Frame Delta", frameDelta)

        # Apply Thresholding on frame resulting from the difference between
        # background frame and current frame. cv2.threshold function outputs
        # 2 variables, the second one is the thresholded image
        thresh = cv2.threshold(frameDelta, project_conf["tresh_min_value"],
                               255, cv2.THRESH_BINARY)[1]

        if project_conf["local_visualization"]:
            cv2.imshow("Tresh", thresh)

        # Dilate the treholded frame to fill the gaps
        thresh = cv2.dilate(thresh, None, iterations=2)

        if project_conf["local_visualization"]:
            cv2.imshow("Tresh dilated 2", thresh)

        # Get contours
        contours, hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                               cv2.CHAIN_APPROX_SIMPLE)

        # Loops through contours to detect moving areas that are bigger than
        # the threshold defined for min_contour_area key and to draw a
        # rectangle around
        for contour in contours:
            if cv2.contourArea(contour) > project_conf["min_contour_area"]:
                (x, y, w, h) = cv2.boundingRect(contour)
                cv2.rectangle(frame_array, (x, y), (x + w, y + h), (0, 255, 0),
                              2)
                motion_detected = True

        # Handle motion detection alert
        if motion_detected:
            # Compute time elapsed since last email sent
            delta_timestamp = motion_frame_timestamp - email_sent_timestamp
            # If time elapsed is superior than the sending interval threshold
            # a new email can be sent
            if delta_timestamp > int(project_conf["email_sending_interval"]):
                # Increase motion counter
                motion_counter += 1
                # If motion counter is superior or equal to the minimum number
                # of frame with motion detected threshold, alert is confirmed
                if motion_counter >= int(project_conf["min_number_motion"]):
                    # Reset motion counter for next occurence
                    motion_counter = 0
                    # Set email timestamp to the motion frame timestamp
                    email_sent_timestamp = motion_frame_timestamp
                    # Set frame file timestamp in a readable format
                    frame_file_timestamp = strftime(
                        "%A%d%B%Y%H%M%S", localtime(motion_frame_timestamp))
                    # Check if the directory to save motion frames exists
                    # if not, create it
                    if path.exists(project_conf["motion_frame_directory"]) \
                            is False:
                        try:
                            mkdir(project_conf["motion_frame_directory"])
                        except OSError as error:
                            print("Error: ", error)
                            exit(0)

                    # Set motion frame file path
                    frame_file_path = project_conf["motion_frame_directory"] +\
                        "/securitycam_{}.jpg".format(frame_file_timestamp)
                    # Save frame array as jpg to motion frame file path
                    cv2.imwrite(frame_file_path, frame_array)
                    # Send an email with the motion frame attached
                    send_email(project_conf, motion_frame_timestamp,
                               frame_file_path)

        if project_conf["local_visualization"]:
            cv2.imshow("Security cam", frame_array)
            cv2.waitKey(10)

        camera_frame.truncate()
        camera_frame.seek(0)
