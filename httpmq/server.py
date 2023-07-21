from flask import Flask, request, jsonify, render_template
from uuid import uuid4
from .config import SERVER_SETTINGS
from .message_queue import MessageQueue
from .models import Message, Session

app = Flask(__name__)
mq = MessageQueue()

def validate_admin():
    if request.args.get("key") == SERVER_SETTINGS["AUTH_KEY"]:
        return True
    if request.headers.get("Authorization") == SERVER_SETTINGS["AUTH_KEY"]:
        return True
    if request.headers.get("Auth-Key") == SERVER_SETTINGS["AUTH_KEY"]:
        return True
    return False

@app.route('/api/register', methods=['POST'])
def register():
    session_id = str(uuid4())
    mq.register(session_id)
    return jsonify(session_id=session_id), 200

@app.route('/api/publish/<path:topic>', methods=['POST'])
def publish(topic):
    data = request.json.get('data')
    ttl = SERVER_SETTINGS['DEFAULT_TTL']
    if 'ttl' in request.json:
        ttl_req = request.json.get('ttl')
        if isinstance(ttl_req, int):
            ttl = ttl_req
        if isinstance(ttl_req, str) and ttl_req.isdigit():
            ttl = int(ttl_req)
        if ttl < 0:
            ttl = SERVER_SETTINGS['NEVER_EXPIRE_TTL']
    message = mq.publish(topic, data, ttl)
    return jsonify(status='success', message_id=message.message_id, timestamp=message.timestamp), 200

@app.route('/api/subscribe', methods=['GET'])
def get_subscribe():
    session_id = request.headers.get('Session-Id')
    if not session_id:
        session_id = request.args.get('session_id')
    session = mq.sessions.get(session_id)
    if session:
        return jsonify({'topics': list(session.subscribed_topics)}), 200
    else:
        return jsonify({'error': 'session_id not found'}), 400

@app.route('/api/subscribe/<path:topic>', methods=['POST'])
def subscribe(topic):
    session_id = request.headers.get('Session-Id')
    if not session_id:
        data = request.get_json(force=True)
        session_id = data.get('session_id')
    if session_id in mq.sessions:
        if mq.subscribe(session_id, topic):
            return jsonify({'status': 'subscribed'}), 200
        else:
            return jsonify({'error': 'topic not found'}), 404
    else:
        return jsonify({'error': 'session_id not found'}), 400

@app.route('/api/subscribe/<path:topic>', methods=['DELETE'])
def unsubscribe(topic):
    session_id = request.json.get('session_id')
    if mq.unsubscribe(session_id, topic):
        return jsonify(status='success'), 200
    else:
        return jsonify(error='topic or subscription not found'), 404

@app.route('/api/receive', methods=['GET'])
def receive():
    mq.expire()
    session_id = request.headers.get('Session-Id')
    if not session_id:
        session_id = request.args.get('session_id')
    if session_id in mq.sessions:
        messages = mq.receive(session_id)
        return jsonify({'messages': [message.to_dict() for message in messages]}), 200
    else:
        return jsonify({'error': 'session not found'}), 404

@app.route('/api/acknowledge', methods=['POST'])
def acknowledge():
    session_id = request.json.get('session_id')
    topic_name = request.json.get('topic')
    message_id = request.json.get('message_id')
    if not session_id or not message_id or not topic_name:
        return jsonify(error='bad request'), 400
    if mq.acknowledge(session_id, topic_name, message_id):
        return jsonify(status='success'), 200
    else:
        return jsonify(error='message invalid or not found'), 404

@app.route('/api/admin/topics', methods=['GET'])
def admin_topics():
    if not validate_admin():
        return jsonify(error='Unauthorized'), 401
    topics = [topic for topic in mq.get_topics()]
    return jsonify(topics=topics), 200

@app.route('/api/admin/messages/<path:topic>', methods=['GET'])
def admin_messages(topic):
    if not validate_admin():
        return jsonify(error='Unauthorized'), 401
    messages = mq.get_messages(topic)
    return jsonify(messages=[message for message in messages]), 200

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return app.send_static_file('admin.html')

@app.route('/tool')
def tool():
    return app.send_static_file('tool.html')

if __name__ == "__main__":
    app.run(debug=True)
