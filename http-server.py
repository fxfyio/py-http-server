import os
import mimetypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote, urlparse
import argparse
import socket
import time


def format_size(size):
    # 将大小转换为更易读的格式
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def send_text_response(self, content, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def list_directory(self, path):
        if not path or path == '/':
            path = "."
        try:
            file_list = os.listdir(path)
        except OSError:
            self.send_error(404, "File not found")
            return None
        file_list.sort(key=lambda a: a.lower())

        content = '<html><head>'
        content += '<meta charset="utf-8">'
        content += '<meta name="viewport" content="width=device-width, initial-scale=1">'
        content += '<title>Python HTTP Server</title>'
        content += '<style>'
        content += '''
            body {
                font-family: Arial, sans-serif;
                background-color: #e2e8f0;
                padding: 20px;
                color: #1a202c;
            }

            .upload-form, .file-list {
                background-color: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 1px 3px 0 rgba(0,0,0,0.1), 0 1px 2px 0 rgba(0,0,0,0.06);
                margin-bottom: 20px;
            }

            input[type="file"], input[type="submit"] {
                width: 100%;
                padding: 10px;
                margin-bottom: 10px;
                border-radius: 5px;
                border: 1px solid #cbd5e0;
                background-color: #edf2f7;
                cursor: pointer;
                font-weight: bold; /* 设置字体为粗体 */
            }

            input[type="submit"] {
                background-color: #4c51bf;
                color: white;
                border: none;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                background-color: white;
                box-shadow: 0 1px 3px 0 rgba(0,0,0,0.1), 0 1px 2px 0 rgba(0,0,0,0.06);
            }

            th, td {
                padding: 10px;
                border: 1px solid #cbd5e0;
                text-align: left;
                border-bottom: none;
                border-top: none;
                border-left: 1px solid #e2e8f0; 
                border-right: none; 
            }

            th {
                background-color: #4c51bf;
                color: white;
            }

            tr:nth-child(even) {
                background-color: #f7f7f7;
            }
            .directory-link {
                color: black; /* 为目录链接设置红色 */
                font-weight: bold; /* 设置字体为粗体 */
            }
        '''
        content += '</style></head><body>'

        content += '<div class="upload-form">'
        content += '<h2>Upload File</h2>'
        content += '<form enctype="multipart/form-data" method="post" action="/">'
        content += '<input type="file" name="file" /><br/>'
        content += '<input type="submit" value="Upload" />'
        content += '</form></div>'

        content += f'<h2>Directory listing for  {os.getcwd()} </h2>'
        content += '<div class="file-list">'
        content += '<table><tr><th>Name</th><th>Last Modified</th><th>Size</th><th>Type</th></tr>'

        for name in file_list:
            fullname = os.path.join(path, name)
            stats = os.stat(fullname)
            modified_time = time.strftime(
                '%Y-%m-%d %H:%M', time.localtime(stats.st_mtime))
            size = format_size(stats.st_size)
            if os.path.isdir(fullname):
                file_type = "Folder"
            else:
                mime_type, _ = mimetypes.guess_type(fullname)
                file_type = mime_type if mime_type else "File"

            displayname = name + "/" if os.path.isdir(fullname) else name
            linkname = name + "/" if os.path.isdir(fullname) else name

            content += '<tr>'
            link_class = "directory-link" if os.path.isdir(fullname) else ""
            content += f'<td><a href="{linkname}" class="{link_class}">{displayname}</a></td>'
            content += f'<td>{modified_time}</td>'
            content += f'<td>{size}</td>'
            content += f'<td>{file_type}</td>'
            content += '</tr>'

        content += '</table></div>'
        content += '</body></html>'
        return content

    def do_GET(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            content = self.list_directory(path)
            if content is not None:
                self.send_text_response(content)
        elif os.path.isfile(path):
            mime_type, _ = mimetypes.guess_type(path)
            if mime_type is None:
                # 如果无法猜测MIME类型，则默认为二进制流
                mime_type = 'application/octet-stream'
            try:
                with open(path, 'rb') as file:
                    self.send_response(200)
                    self.send_header(
                        'Content-type', f'{mime_type}; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(file.read())
            except OSError:
                self.send_error(404, "File not found")
        else:
            self.send_error(404, "File not found")

    def translate_path(self, path):
        # 解析URL路径
        parsed_path = urlparse(path)
        path = parsed_path.path
        path = unquote(path)
        # 防止路径遍历
        path = path.replace('../', '').replace('..\\', '')
        # 如果是根目录，设置为当前目录
        if path == '/':
            return '.'
        return path.lstrip('/')

    def do_POST(self):
        # 获取请求的内容长度
        content_length = int(self.headers['Content-Length'])
        # 读取请求体
        post_data = self.rfile.read(content_length)

        # 解析请求体以获取文件数据
        lines = post_data.split(b'\r\n')
        in_file_data = False
        file_data = []
        filename = None
        for line in lines:
            if line.startswith(b'Content-Disposition'):
                # 解析出文件名
                parts = line.split(b';')
                for part in parts:
                    if b'filename=' in part:
                        filename = part.split(b'=')[1].strip(b'"\'')
            elif line == b'':
                if in_file_data:
                    # 文件内容的结尾
                    break
                else:
                    # 文件内容的开始
                    in_file_data = True
            elif in_file_data:
                file_data.append(line)

        # 去除头尾的额外数据
        file_data = file_data[:-1]

        if filename and file_data:
            # 写入文件
            filepath = os.path.join('.', filename.decode())
            with open(filepath, 'wb') as file:
                for line in file_data:
                    file.write(line + b'\r\n')

            # 文件上传成功后
            self.send_response(302)  # 发送302重定向响应
            self.send_header('Location', '/')  # 设置重定向到根目录
            self.end_headers()
        else:
            self.send_error(400, "File upload failed")


def get_local_ip():
    # 获取本地主机名
    hostname = socket.gethostname()
    # 获取所有局域网 IP 地址
    ip_addresses = socket.gethostbyname_ex(hostname)[2]
    return ip_addresses


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Simple HTTP Server with Port and Directory options')
    parser.add_argument('-p', '--port', type=int, default=8000,
                        help='Port number to run the server on')
    args = parser.parse_args()

    server_address = ('0.0.0.0', args.port)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)

    ip_addresses = get_local_ip()

    print(
        f"Starting up http-server, serving {os.getcwd()}")
    print("\nAvailable on:")
    print(f"  http://127.0.0.1:{args.port}")
    for ip_address in ip_addresses:
        print(f"  http://{ip_address}:{args.port}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
