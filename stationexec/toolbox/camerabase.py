# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
This is a camera class to extend the base Tool class. This restricts the Tool interface further
with camera specific functionality. This class should be used as the base for creating any camera
driver.

Adds the required methods:

 * capture_image
 * set_exposure

And the optional methods:

 * begin_video_stream
 * end_video_stream
"""
from datetime import datetime
import asyncio

import cv2
import numpy as np

from stationexec.logger import log
from stationexec.toolbox.tool import Tool
from stationexec.utilities.ioloop_ref import IoLoop
from stationexec.web.handlers import ExecutiveHandler


class CameraBase(Tool):
    def __init__(
        self,
        frames_per_second=15,
        stream_image_width=460,
        stream_image_height=329,
        **kwargs
    ):
        super(CameraBase, self).__init__(**kwargs)
        self.latest_image = None
        self.latest_image_timestamp = None
        self.last_processed = None
        self.is_capturing = False
        self.is_streaming = False

        self.stream_image_width = stream_image_width
        self.stream_image_height = stream_image_height

        self.frames_per_second = frames_per_second
        self.stream_loop_delay = 1.0 / float(frames_per_second * 2)
        self.stream_color_mode = cv2.COLOR_BAYER_BG2RGB

        self.has_been_disconnected = False

    def get_endpoints(self):
        base_url = self._get_tool_url()
        endpoints = [
            (
                r"{0}/stream".format(base_url),
                CameraStreamHandler,
                {
                    'get_latest': self.get_latest,
                    'width': self.stream_image_width,
                    'height': self.stream_image_height,
                    'fps': self.frames_per_second,
                },
            ),
        ]
        return endpoints

    def capture_image(self):
        """
        Capture and return camera image

        :return: None
        """
        raise NotImplementedError

    def get_latest(self):
        return self.process_image()

    def get_latest_raw(self):
        return self.latest_image

    def set_exposure(self, exposure):
        """
        Set the camera exposure value

        :return: None
        """
        raise NotImplementedError

    def start_capture(self, message="Capturing"):
        """
        Start video/constant capture on the camera

        :param str message: Optional status message to indicate camera in capture mode

        :return: None
        """
        raise NotImplementedError

    def stop_capture(self):
        """
        Stop the video/constant capture

        :return: None
        """
        raise NotImplementedError

    def begin_video_stream(self):
        """
        Start the camera capturing and launch the 'run' loop that grabs, processes,
         and caches the latest image from the camera for streaming to the UI or
         for ease of grabbing the latest image

        :return: None
        """
        if not self.is_streaming:
            self.start_capture("Streaming to UI")
            IoLoop().current().spawn_callback(self.run)

    def end_video_stream(self):
        """
        Terminate video streaming

        :return: None
        """
        self.stop_capture()

    async def run(self):
        """
        Routine spawned by begin_video_stream that runs continuously to grab
        latest image from camera and cache it. Exits on error or on call to
        end_video_stream. Can check status of loop with boolean self.is_streaming

        :return: None
        """
        log.debug(2, "Begin capture loop for {0}".format(self.tool_id))
        while self.is_capturing:
            self.is_streaming = True
            await asyncio.sleep(self.stream_loop_delay)
            # yield gen.sleep(self.stream_loop_delay)
            try:
                image_data = self.capture_stream_image()
                if image_data is not None:
                    self.save_image(image_data)
            except Exception as e:
                log.exception("Camera exception while streaming", e)
                self.shutdown()
                break
        log.debug(2, "End capture loop for {0}".format(self.tool_id))
        self.is_streaming = False

    def capture_stream_image(self):
        """
        Capture and return camera image for video stream

        :return: None
        """
        raise NotImplementedError

    def set_stream_color_mode(self, color_mode):
        self.stream_color_mode = color_mode

    def save_image(self, image_data):
        """
        Save copy of the raw image with a timestamp for later use

        :param image_data:
        :return:
        """
        # Save and timestamp image data
        self.latest_image = image_data
        self.latest_image_timestamp = datetime.now()

    def process_image(self):
        """
        Process saved raw image for streaming

        :return:
        """
        if self.latest_image is None:
            return None

        # if not self.is_streaming:
        #     return self.last_processed

        # Convert encoded image to desired color space
        # stream_image = cv2.cvtColor(self.latest_image, self.stream_color_mode)

        # Resize image to streaming size
        stream_image = cv2.resize(
            self.latest_image, (self.stream_image_width, self.stream_image_height)
        )

        # Convert to JPEG for streaming
        retval, data = cv2.imencode(
            ".jpg", stream_image, [cv2.IMWRITE_JPEG_QUALITY, 100]
        )

        self.last_processed = data.tobytes()

        return self.last_processed

    def initialize(self):
        raise NotImplementedError

    def verify_status(self):
        raise NotImplementedError

    def shutdown(self):
        raise NotImplementedError

    def on_ui_command(self, command, **kwargs):
        pass


class CameraStreamHandler(ExecutiveHandler):
    get_latest = None  # type: function
    no_image_yet = None  # type: str
    fps = None  # type: int

    def initialize(self, **kwargs):
        """Prepare to handle endpoint operation"""
        width = kwargs.get("width")
        height = kwargs.get("height")
        self.get_latest = kwargs.get("get_latest")
        # Limit streaming FPS to 15 to give CPU a chance
        fps = min(kwargs.get("fps", 15), 15)
        self.stream_delay = 1.0 / float(fps)

        _, data = cv2.imencode(
            ".jpg",
            np.zeros((height, width, 3), np.uint8),
            [cv2.IMWRITE_JPEG_QUALITY, 100],
        )
        self.no_image_yet = data.tobytes()

    async def get(self):
        # Inspired by
        # https://blog.miguelgrinberg.com/post/video-streaming-with-flask
        # https://stackoverflow.com/questions/20018684/tornado-streaming-http-response-as-asynchttpclient-receives-chunks
        self.set_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        while True:
            frame = self.get_latest()
            if frame is None:
                frame = self.no_image_yet
            self.write("--frame\r\n")
            self.write("Content-Type: image/jpeg\r\n\r\n")
            self.write(frame)
            await self.flush()
            await asyncio.sleep(self.stream_delay)
