import http.server
import socketserver
import json
import urllib.request
import os

PORT = 8080

class VerifyHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def guess_type(self, path):
        ctype = super().guess_type(path)
        if ctype.startswith('application/json') or path.endswith('.json'):
            return 'application/json; charset=utf-8'
        return ctype
    def do_GET(self):
        if self.path.startswith('/deal'):
            import urllib.parse
            import subprocess
            import glob
            import os
            
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            target = query.get('target', ['10'])[0]
            
            try:
                subprocess.run(["python", "dealer.py", "artline.json", "--players", "1", "--target", target], check=True)
                
                files = glob.glob("game_*.json")
                if not files:
                    self.send_error(500, "Dealer failed to create game file")
                    return
                    
                newest = max(files, key=os.path.getctime)
                with open(newest, 'r', encoding='utf-8') as f:
                    data = f.read()
                    
                os.remove(newest)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(data.encode('utf-8'))
            except Exception as e:
                print("Dealer Error:", e)
                self.send_error(500, str(e))
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/update_image':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            item_id = data.get('id')
            new_url = data.get('url')
            
            if not item_id or not new_url:
                self.send_error(400, 'Bad Request')
                return
                
            print(f"Updating {item_id} with URL: {new_url}")
            
            try:
                # 1. Download image
                req = urllib.request.Request(new_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                image_path = f"images/{item_id}.jpg"
                with urllib.request.urlopen(req) as response, open(image_path, 'wb') as out_file:
                    out_file.write(response.read())
                
                # 2. Update JSON
                with open('artline.json', 'r', encoding='utf-8') as f:
                    data_json = json.load(f)
                
                for item in data_json:
                    if item['id'] == item_id:
                        item['image_local'] = image_path
                        item['image'] = new_url
                        item['source'] = 'manual'
                        break
                        
                with open('artline.json', 'w', encoding='utf-8') as f:
                    json.dump(data_json, f, indent=2, ensure_ascii=False)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'path': f"{image_path}?t={os.path.getmtime(image_path)}"}).encode('utf-8'))
                
            except Exception as e:
                print("Error:", e)
                self.send_error(500, str(e))
        else:
            self.send_error(404, 'Not Found')

# Start server
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), VerifyHandler) as httpd:
    print(f"Serving Verification Dashboard at http://localhost:{PORT}/verify.html")
    httpd.serve_forever()
