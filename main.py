from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import pathlib
import mimetypes
import json
import logging
import socket
from threading import Thread
from datetime import datetime


BASE_DIR = pathlib.Path()
SERVER_IP = '0.0.0.0'
HTTP_PORT = 3000
SOCKET_PORT = 5000
STORAGE_DIR = pathlib.Path().joinpath('storage')
FILE_STORAGE = STORAGE_DIR / 'data.json'
BUFFER = 1024


class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urllib.parse.urlparse(self.path)
        match route.path:
            case '/':
                self.send_html_file('index.html')
            case '/message':
                self.send_html_file('message.html')
            case _:
                file = BASE_DIR / route.path[1:]
                if file.exists():
                    self.send_static_file(file)
                else:
                    self.send_html_file('error.html', 404)

    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        send_data_to_socket(body)
        self.send_response(302)
        self.send_header('Location', '/message')
        self.end_headers()

    def send_html_file(self, filename, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        with open(filename, 'rb') as fd:
            self.wfile.write(fd.read())

    def send_static_file(self, filename):
        self.send_response(200)
        mime_type, *rest = mimetypes.guess_type(filename)
        if mime_type:
            self.send_header('Content-Type', mime_type)
        else:
            self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        with open(filename, 'rb') as f:
            self.wfile.write(f.read())


def send_data_to_socket(body):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.sendto(body, (SERVER_IP, SOCKET_PORT))
    client_socket.close()


def run_http_server(server_class=HTTPServer, handler_class=HttpHandler):
    http_server = server_class((SERVER_IP, HTTP_PORT), handler_class)
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        http_server.server_close()


def save_data(data):
    body = urllib.parse.unquote_plus(data.decode())

    try:
        if FILE_STORAGE.exists():
            with open(FILE_STORAGE, 'r') as f:
                messages = json.load(f)
        else:
            STORAGE_DIR.mkdir(exist_ok=True)
            messages = {}

        payload = {key: value for key, value in [el.split('=') for el in body.split('&')]}
        messages.update({str(datetime.now()): payload})

        with open(FILE_STORAGE, 'w', encoding='utf-8') as fd:
            json.dump(messages, fd, ensure_ascii=False)
    except ValueError as err:
        logging.error(f"Field parse data {body} with error {err}")
    except OSError as err:
        logging.error(f"Field write data {body} with error {err}")


def run_socket_server(ip, port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server = ip, port
    server_socket.bind(server)
    try:
        while True:
            data, address = server_socket.recvfrom(BUFFER)
            save_data(data)
    except KeyboardInterrupt:
        logging.info('Socket server stopped')
    finally:
        server_socket.close()


if __name__ == '__main__':
    thread_http = Thread(target=run_http_server)
    thread_http.start()

    thread_socket = Thread(target=run_socket_server(SERVER_IP, SOCKET_PORT))
    thread_socket.start()
