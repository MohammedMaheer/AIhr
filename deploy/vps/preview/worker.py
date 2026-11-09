"""Single-job Unix-socket converter. Run only in the network-disabled container."""
import http.server
import io
import os
from pathlib import Path
import signal
import socket
import socketserver
import subprocess
import tempfile
import zipfile

MAX_INPUT = 16 * 1024 * 1024
MAX_OUTPUT = 32 * 1024 * 1024
PROFILE = '''<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting">
<prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop>
<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
</oor:items>'''


def valid_word(content, extension):
    if extension == 'doc':
        return content.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            return (len(entries) <= 5000 and sum(entry.file_size for entry in entries) <= 80 * 1024 * 1024
                    and {'[Content_Types].xml', 'word/document.xml'} <= names
                    and not any(entry.flag_bits & 1 for entry in entries)
                    and not any('vbaproject' in name.lower() for name in names))
    except (OSError, ValueError, zipfile.BadZipFile):
        return False


def convert(content, extension):
    if extension not in ('doc', 'docx') or not valid_word(content, extension):
        raise ValueError('Unsupported or invalid Word document')
    with tempfile.TemporaryDirectory(prefix='preview-') as directory:
        root = Path(directory)
        source = root / ('document.' + extension)
        source.write_bytes(content)
        profile = root / 'profile' / 'user'
        profile.mkdir(parents=True)
        (profile / 'registrymodifications.xcu').write_text(PROFILE, encoding='utf-8')
        command = ['libreoffice', '-env:UserInstallation=' + (root / 'profile').as_uri(),
                   '--headless', '--nologo', '--nodefault', '--nofirststartwizard', '--norestore',
                   '--convert-to', 'pdf:writer_pdf_Export', '--outdir', str(root), str(source)]
        environment = {'PATH':'/usr/local/bin:/usr/bin:/bin', 'HOME':str(root), 'TMPDIR':str(root),
                       'LANG':'C.UTF-8', 'SAL_USE_VCLPLUGIN':'svp', 'SAL_DISABLE_OPENCL':'1'}
        with subprocess.Popen(command, env=environment, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, start_new_session=True) as process:
            try:
                if process.wait(timeout=30) != 0:
                    raise ValueError('Conversion failed')
            except subprocess.TimeoutExpired as error:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise ValueError('Conversion timed out') from error
        output = root / 'document.pdf'
        if not output.is_file() or output.stat().st_size > MAX_OUTPUT:
            raise ValueError('No bounded PDF output')
        data = output.read_bytes()
        if not data.startswith(b'%PDF-'):
            raise ValueError('Invalid PDF output')
        return data


class Server(http.server.HTTPServer):
    address_family = socket.AF_UNIX

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = 'preview', 0


class Handler(http.server.BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(40)
        super().setup()

    def log_message(self, *_):
        pass

    def reply(self, status, content, content_type='text/plain'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        self.reply(200 if self.path == '/health' else 404, b'ok')

    def do_POST(self):
        extension = self.path.removeprefix('/convert/')
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = 0
        if self.path not in ('/convert/doc', '/convert/docx') or not 0 < length <= MAX_INPUT or self.headers.get('Transfer-Encoding'):
            self.reply(400, b'Invalid request')
            return
        content = self.rfile.read(length)
        if len(content) != length:
            self.reply(400, b'Incomplete document')
            return
        try:
            self.reply(200, convert(content, extension), 'application/pdf')
        except (ValueError, OSError):
            self.reply(422, b'Document cannot be converted')


if __name__ == '__main__':
    address = Path('/run/preview/renderer.sock')
    address.unlink(missing_ok=True)
    with Server(str(address), Handler) as server:
        address.chmod(0o600)
        server.serve_forever()
