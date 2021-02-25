# Web streaming example
# Source code from the official PiCamera package
# http://picamera.readthedocs.io/en/latest/recipes2.html#web-streaming

import io
import os
import picamera
import logging
import socketserver
from threading import Condition
from http import server

PAGE = """\
<!DOCTYPE html>
<html lang="de">
<head>
  <meta http-equiv=content-type content="text/html; charset=utf-8" />
  <meta http-equiv="Cache-Control" content="private, no-transform" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>RaspberryPI based Dokumentenkamera (EL-Pi)</title>
  <style>
    #header {
      position: absolute;
	  text-align: center;
	  font-family: Arial, Helvetica, sans-serif;
	  z-index: 1;
    }
	#content {
	  position: absolute;
      width: 100%;
      top: 0;
      left: 0;
	  bottom: 0;
      margin: 0;
	}
	#footer {
	  position: absolute;
	  bottom: 5px;
	  font-family: Arial, Helvetica, sans-serif;
	}
	#content img{
	  position: relative;
	  top: 0px;
	  width: 100%;
	  height: 100%;
	}
  </style>
</head>
<body>
	<div id="header">RPI DocCam</div>
	<div id="content"><img id="doccam" src="stream.mjpg"></div>
  <div id="footer"><button onclick="window.location.href='./shutdown.html'">Shutdown RPI-DocCam</button></div>
<script>
  var counter;
	counter = 0;
	var img = document.getElementById('doccam');
	img.style.transform = 'rotate(' + 90 * (counter + 1) + 'deg)';
	img.onclick = function() {
		console.log(counter);
    console.log(img.style.transform);
    img.style.transform = 'rotate(' + 90 * (counter + 1) + 'deg)';
		console.log(img.style.transform);
    counter += 1;
		console.log(counter);
  }
</script>
</body>
</html>
"""


class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/shutdown.html':
            content = "Shutting down RPI-DocCam".encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
            os.system("sudo shutdown now")
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with picamera.PiCamera(resolution='640x480', framerate=24) as camera:
        output = StreamingOutput()
        # Uncomment the next line to change your Pi's Camera rotation (in degrees)
        # camera.rotation = 90
        camera.start_recording(output, format='mjpeg')
        try:
            address = ('', 8000)
            server = StreamingServer(address, StreamingHandler)
            server.serve_forever()
        finally:
            camera.stop_recording()
