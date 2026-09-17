import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify, g

app = Flask(__name__)
app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), 'todos.db')
app.config['JSON_AS_ASCII'] = False

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT DEFAULT '일반',
            priority TEXT DEFAULT 'medium',
            due_date TEXT,
            completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db.commit()

    # 초기 샘플 데이터가 없으면 예시 데이터 삽입
    cursor = db.execute('SELECT COUNT(*) as count FROM todos')
    if cursor.fetchone()['count'] == 0:
        sample_todos = [
            ('Flask 웹 애플리케이션 구조 설계', 'REST API와 SQLite 데이터베이스 스키마 완성하기', '업무', 'high', '2026-09-17', 1),
            ('할일 관리 UI/UX 디자인 개선', '모던 글래스모피즘 및 다크/라이트 테마 적용', '업무', 'high', '2026-09-18', 0),
            ('Python 백엔드 연동 테스트', 'CRUD API 및 단위 테스트 코드 작성 및 실행', '공부', 'medium', '2026-09-19', 0),
            ('가벼운 운동 및 산책하기', '하루 30분 유산소 운동으로 건강 챙기기', '건강', 'low', '2026-09-20', 0),
            ('주간 회의 자료 준비', '다음 주 진행될 프로젝트 스프린트 계획 수립', '개인', 'medium', '2026-09-22', 0),
        ]
        db.executemany('''
            INSERT INTO todos (title, description, category, priority, due_date, completed)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_todos)
        db.commit()

# 메인 페이지 라우트
@app.route('/')
def index():
    return render_template('index.html')

# Health Check 라우트
@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'message': 'Todo Application backend is running smoothly',
        'timestamp': datetime.now().isoformat()
    })

# Todo 목록 조회 API (검색, 필터링, 정렬 지원)
@app.route('/api/todos', methods=['GET'])
def get_todos():
    status = request.args.get('status', 'all') # all, active, completed
    category = request.args.get('category', 'all')
    priority = request.args.get('priority', 'all')
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by', 'created_at') # created_at, due_date, priority, title
    order = request.args.get('order', 'desc').lower() # asc, desc

    query = 'SELECT * FROM todos WHERE 1=1'
    params = []

    if status == 'active':
        query += ' AND completed = 0'
    elif status == 'completed':
        query += ' AND completed = 1'

    if category and category != 'all':
        query += ' AND category = ?'
        params.append(category)

    if priority and priority != 'all':
        query += ' AND priority = ?'
        params.append(priority)

    if search:
        query += ' AND (title LIKE ? OR description LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])

    # 정렬 기준
    allowed_sort_fields = {
        'created_at': 'created_at',
        'due_date': 'CASE WHEN due_date IS NULL OR due_date = "" THEN 1 ELSE 0 END, due_date',
        'priority': 'CASE priority WHEN "high" THEN 1 WHEN "medium" THEN 2 WHEN "low" THEN 3 ELSE 4 END',
        'title': 'title'
    }
    sort_sql = allowed_sort_fields.get(sort_by, 'created_at')
    order_sql = 'DESC' if order == 'desc' else 'ASC'

    # completed 항목은 맨 뒤로 배치하되 우선순위/날짜 정렬 유지
    query += f' ORDER BY completed ASC, {sort_sql} {order_sql}'

    db = get_db()
    cursor = db.execute(query, params)
    todos = [dict(row) for row in cursor.fetchall()]
    return jsonify(todos)

# Todo 단일 조회 API
@app.route('/api/todos/<int:todo_id>', methods=['GET'])
def get_todo(todo_id):
    db = get_db()
    cursor = db.execute('SELECT * FROM todos WHERE id = ?', (todo_id,))
    row = cursor.fetchone()
    if row is None:
        return jsonify({'error': 'Todo not found'}), 404
    return jsonify(dict(row))

# Todo 추가 API
@app.route('/api/todos', methods=['POST'])
def add_todo():
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Title is required'}), 400

    description = data.get('description', '').strip()
    category = data.get('category', '일반').strip() or '일반'
    priority = data.get('priority', 'medium').strip()
    if priority not in ['low', 'medium', 'high']:
        priority = 'medium'
    due_date = data.get('due_date', '').strip()

    db = get_db()
    cursor = db.execute('''
        INSERT INTO todos (title, description, category, priority, due_date, completed)
        VALUES (?, ?, ?, ?, ?, 0)
    ''', (title, description, category, priority, due_date))
    db.commit()

    new_id = cursor.lastrowid
    new_todo = db.execute('SELECT * FROM todos WHERE id = ?', (new_id,)).fetchone()
    return jsonify(dict(new_todo)), 201

# Todo 수정 API
@app.route('/api/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id):
    data = request.get_json() or {}
    db = get_db()
    todo = db.execute('SELECT * FROM todos WHERE id = ?', (todo_id,)).fetchone()
    if not todo:
        return jsonify({'error': 'Todo not found'}), 404

    title = data.get('title', todo['title']).strip()
    if not title:
        return jsonify({'error': 'Title cannot be empty'}), 400

    description = data.get('description', todo['description'])
    category = data.get('category', todo['category'])
    priority = data.get('priority', todo['priority'])
    due_date = data.get('due_date', todo['due_date'])
    completed = 1 if data.get('completed', todo['completed']) else 0

    db.execute('''
        UPDATE todos
        SET title = ?, description = ?, category = ?, priority = ?, due_date = ?, completed = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (title, description, category, priority, due_date, completed, todo_id))
    db.commit()

    updated = db.execute('SELECT * FROM todos WHERE id = ?', (todo_id,)).fetchone()
    return jsonify(dict(updated))

# Todo 완료 상태 토글 API
@app.route('/api/todos/<int:todo_id>/toggle', methods=['PATCH'])
def toggle_todo(todo_id):
    db = get_db()
    todo = db.execute('SELECT * FROM todos WHERE id = ?', (todo_id,)).fetchone()
    if not todo:
        return jsonify({'error': 'Todo not found'}), 404

    new_status = 0 if todo['completed'] == 1 else 1
    db.execute('''
        UPDATE todos
        SET completed = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (new_status, todo_id))
    db.commit()

    updated = db.execute('SELECT * FROM todos WHERE id = ?', (todo_id,)).fetchone()
    return jsonify(dict(updated))

# Todo 삭제 API
@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    db = get_db()
    cursor = db.execute('DELETE FROM todos WHERE id = ?', (todo_id,))
    db.commit()
    if cursor.rowcount == 0:
        return jsonify({'error': 'Todo not found'}), 404
    return jsonify({'success': True, 'message': 'Todo deleted successfully'})

# 완료된 Todo 일괄 삭제 API
@app.route('/api/todos/completed', methods=['DELETE'])
def delete_completed_todos():
    db = get_db()
    cursor = db.execute('DELETE FROM todos WHERE completed = 1')
    db.commit()
    return jsonify({'success': True, 'deleted_count': cursor.rowcount})

# 통계 API
@app.route('/api/stats', methods=['GET'])
def get_stats():
    db = get_db()
    total = db.execute('SELECT COUNT(*) as count FROM todos').fetchone()['count']
    completed = db.execute('SELECT COUNT(*) as count FROM todos WHERE completed = 1').fetchone()['count']
    pending = total - completed
    rate = round((completed / total * 100), 1) if total > 0 else 0

    # 카테고리별 통계
    cat_cursor = db.execute('''
        SELECT category, COUNT(*) as count, SUM(completed) as completed_count
        FROM todos
        GROUP BY category
    ''')
    categories = [
        {
            'category': row['category'],
            'total': row['count'],
            'completed': row['completed_count'] or 0
        }
        for row in cat_cursor.fetchall()
    ]

    # 우선순위별 통계
    priority_cursor = db.execute('''
        SELECT priority, COUNT(*) as count, SUM(completed) as completed_count
        FROM todos
        GROUP BY priority
    ''')
    priorities = {
        row['priority']: {
            'total': row['count'],
            'completed': row['completed_count'] or 0
        }
        for row in priority_cursor.fetchall()
    }

    return jsonify({
        'total': total,
        'completed': completed,
        'pending': pending,
        'completion_rate': rate,
        'categories': categories,
        'priorities': priorities
    })

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
