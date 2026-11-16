"""Start the local app and open its landing page in the default browser."""
import os, threading, webbrowser
from http.server import ThreadingHTTPServer
import server

def main():
    host=os.environ.get('DESKTER_HOST','127.0.0.1')
    port=int(os.environ.get('DESKTER_PORT','8000'))
    server.init()
    try:http=ThreadingHTTPServer((host,port),server.Handler)
    except OSError as error:
        print(f'Cannot start Deskter on port {port}: {error}. Close the previous server or choose another DESKTER_PORT.')
        return 1
    url=f'http://127.0.0.1:{port}/'
    print(f'Deskter is running at {url}\nKeep this window open. Press Ctrl+C to stop.',flush=True)
    threading.Timer(0.5,lambda:webbrowser.open(url)).start()
    try:http.serve_forever()
    except KeyboardInterrupt:pass
    finally:http.server_close()
    return 0
if __name__=='__main__':raise SystemExit(main())
