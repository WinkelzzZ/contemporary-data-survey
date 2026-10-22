import uuid
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db
from auth import login_required

survey_bp = Blueprint('survey', __name__)


@survey_bp.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    surveys = list(db.surveys.find(
        {'creator_id': ObjectId(session['user_id'])}
    ).sort('created_at', -1))

    for s in surveys:
        s['response_count'] = db.responses.count_documents({'survey_id': s['_id']})
        s['question_count'] = db.questions.count_documents({'survey_id': s['_id']})

    return render_template('dashboard.html', surveys=surveys)


@survey_bp.route('/survey/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'GET':
        return render_template('create_survey.html')

    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    allow_anonymous = request.form.get('allow_anonymous') == 'on'
    deadline_str = request.form.get('deadline', '').strip()
    max_responses_str = request.form.get('max_responses', '').strip()

    if not title:
        flash('问卷标题不能为空', 'error')
        return redirect(url_for('survey.create'))

    deadline = None
    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('截止时间格式错误', 'error')
            return redirect(url_for('survey.create'))

    max_responses = None
    if max_responses_str:
        try:
            max_responses = int(max_responses_str)
            if max_responses <= 0:
                raise ValueError
        except ValueError:
            flash('最大回复数必须为正整数', 'error')
            return redirect(url_for('survey.create'))

    db = get_db()
    survey_key = uuid.uuid4().hex[:8]

    result = db.surveys.insert_one({
        'creator_id': ObjectId(session['user_id']),
        'title': title,
        'description': description,
        'allow_anonymous': allow_anonymous,
        'status': 'draft',
        'deadline': deadline,
        'max_responses': max_responses,
        'survey_key': survey_key,
        'created_at': datetime.now(),
        'updated_at': datetime.now()
    })

    return redirect(url_for('survey.edit', survey_id=str(result.inserted_id)))


@survey_bp.route('/survey/<survey_id>/edit')
@login_required
def edit(survey_id):
    db = get_db()
    survey = db.surveys.find_one({'_id': ObjectId(survey_id)})

    if not survey:
        flash('问卷不存在', 'error')
        return redirect(url_for('survey.dashboard'))

    if str(survey['creator_id']) != session['user_id']:
        flash('无权访问该问卷', 'error')
        return redirect(url_for('survey.dashboard'))

    questions = list(db.questions.find(
        {'survey_id': survey['_id']}
    ).sort('order', 1))

    all_questions_for_jump = [
        {'id': str(q['_id']), 'order': q['order'], 'title': q['title']}
        for q in questions
    ]

    response_count = db.responses.count_documents({'survey_id': survey['_id']})

    return render_template('edit_survey.html',
                           survey=survey,
                           questions=questions,
                           all_questions=all_questions_for_jump,
                           response_count=response_count)


@survey_bp.route('/survey/<survey_id>/settings', methods=['POST'])
@login_required
def update_settings(survey_id):
    db = get_db()
    survey = db.surveys.find_one({'_id': ObjectId(survey_id)})

    if not survey or str(survey['creator_id']) != session['user_id']:
        flash('无权操作', 'error')
        return redirect(url_for('survey.dashboard'))

    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    allow_anonymous = request.form.get('allow_anonymous') == 'on'
    deadline_str = request.form.get('deadline', '').strip()
    max_responses_str = request.form.get('max_responses', '').strip()

    if not title:
        flash('问卷标题不能为空', 'error')
        return redirect(url_for('survey.edit', survey_id=survey_id))

    deadline = None
    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('截止时间格式错误', 'error')
            return redirect(url_for('survey.edit', survey_id=survey_id))

    max_responses = None
    if max_responses_str:
        try:
            max_responses = int(max_responses_str)
            if max_responses <= 0:
                raise ValueError
        except ValueError:
            flash('最大回复数必须为正整数', 'error')
            return redirect(url_for('survey.edit', survey_id=survey_id))

    db.surveys.update_one(
        {'_id': ObjectId(survey_id)},
        {'$set': {
            'title': title,
            'description': description,
            'allow_anonymous': allow_anonymous,
            'deadline': deadline,
            'max_responses': max_responses,
            'updated_at': datetime.now()
        }}
    )

    flash('设置已保存', 'success')
    return redirect(url_for('survey.edit', survey_id=survey_id))


@survey_bp.route('/survey/<survey_id>/publish', methods=['POST'])
@login_required
def publish(survey_id):
    db = get_db()
    survey = db.surveys.find_one({'_id': ObjectId(survey_id)})

    if not survey or str(survey['creator_id']) != session['user_id']:
        flash('无权操作', 'error')
        return redirect(url_for('survey.dashboard'))

    question_count = db.questions.count_documents({'survey_id': survey['_id']})
    if question_count == 0:
        flash('至少需要添加一道题目才能发布', 'error')
        return redirect(url_for('survey.edit', survey_id=survey_id))

    db.surveys.update_one(
        {'_id': ObjectId(survey_id)},
        {'$set': {'status': 'published', 'updated_at': datetime.now()}}
    )

    flash('问卷已发布', 'success')
    return redirect(url_for('survey.edit', survey_id=survey_id))


@survey_bp.route('/survey/<survey_id>/close', methods=['POST'])
@login_required
def close(survey_id):
    db = get_db()
    survey = db.surveys.find_one({'_id': ObjectId(survey_id)})

    if not survey or str(survey['creator_id']) != session['user_id']:
        flash('无权操作', 'error')
        return redirect(url_for('survey.dashboard'))

    db.surveys.update_one(
        {'_id': ObjectId(survey_id)},
        {'$set': {'status': 'closed', 'updated_at': datetime.now()}}
    )

    flash('问卷已关闭', 'success')
    return redirect(url_for('survey.edit', survey_id=survey_id))


@survey_bp.route('/survey/<survey_id>/question/add', methods=['POST'])
@login_required
def add_question(survey_id):
    db = get_db()
    survey = db.surveys.find_one({'_id': ObjectId(survey_id)})

    if not survey or str(survey['creator_id']) != session['user_id']:
        flash('无权操作', 'error')
        return redirect(url_for('survey.dashboard'))

    q_type = request.form.get('type', 'single_choice')
    title = request.form.get('title', '').strip()
    required = request.form.get('required') == 'on'

    if not title:
        flash('题目标题不能为空', 'error')
        return redirect(url_for('survey.edit', survey_id=survey_id))

    valid_types = ['single_choice', 'multiple_choice', 'text_fill', 'number_fill']
    if q_type not in valid_types:
        flash('无效的题目类型', 'error')
        return redirect(url_for('survey.edit', survey_id=survey_id))

    max_order = db.questions.find_one(
        {'survey_id': survey['_id']},
        sort=[('order', -1)]
    )
    next_order = (max_order['order'] + 1) if max_order else 1

    options = []
    if q_type in ('single_choice', 'multiple_choice'):
        raw_options = request.form.getlist('options[]')
        options = [o.strip() for o in raw_options if o.strip()]
        if not options:
            options = ['选项1', '选项2']

    validation = _build_validation(q_type, request.form)
    jump_rules = _build_jump_rules(request.form, db, survey['_id'])

    db.questions.insert_one({
        'survey_id': survey['_id'],
        'order': next_order,
        'type': q_type,
        'title': title,
        'required': required,
        'options': options,
        'validation': validation,
        'jump_rules': jump_rules
    })

    flash('题目已添加', 'success')
    return redirect(url_for('survey.edit', survey_id=survey_id))


@survey_bp.route('/survey/<survey_id>/question/<question_id>/update', methods=['POST'])
@login_required
def update_question(survey_id, question_id):
    db = get_db()
    survey = db.surveys.find_one({'_id': ObjectId(survey_id)})

    if not survey or str(survey['creator_id']) != session['user_id']:
        flash('无权操作', 'error')
        return redirect(url_for('survey.dashboard'))

    question = db.questions.find_one({
        '_id': ObjectId(question_id),
        'survey_id': survey['_id']
    })
    if not question:
        flash('题目不存在', 'error')
        return redirect(url_for('survey.edit', survey_id=survey_id))

    q_type = request.form.get('type', question['type'])
    title = request.form.get('title', '').strip()
    required = request.form.get('required') == 'on'

    if not title:
        flash('题目标题不能为空', 'error')
        return redirect(url_for('survey.edit', survey_id=survey_id))

    options = []
    if q_type in ('single_choice', 'multiple_choice'):
        raw_options = request.form.getlist('options[]')
        options = [o.strip() for o in raw_options if o.strip()]
        if not options:
            options = ['选项1', '选项2']

    validation = _build_validation(q_type, request.form)
    jump_rules = _build_jump_rules(request.form, db, survey['_id'])

    db.questions.update_one(
        {'_id': ObjectId(question_id)},
        {'$set': {
            'type': q_type,
            'title': title,
            'required': required,
            'options': options,
            'validation': validation,
            'jump_rules': jump_rules
        }}
    )

    flash('题目已更新', 'success')
    return redirect(url_for('survey.edit', survey_id=survey_id))


@survey_bp.route('/survey/<survey_id>/question/<question_id>/delete', methods=['POST'])
@login_required
def delete_question(survey_id, question_id):
    db = get_db()
    survey = db.surveys.find_one({'_id': ObjectId(survey_id)})

    if not survey or str(survey['creator_id']) != session['user_id']:
        flash('无权操作', 'error')
        return redirect(url_for('survey.dashboard'))

    deleted = db.questions.delete_one({
        '_id': ObjectId(question_id),
        'survey_id': survey['_id']
    })

    if deleted.deleted_count:
        _reorder_questions(db, survey['_id'])
        _clean_jump_rules(db, survey['_id'], question_id)
        flash('题目已删除', 'success')
    else:
        flash('题目不存在', 'error')

    return redirect(url_for('survey.edit', survey_id=survey_id))


@survey_bp.route('/survey/<survey_id>/question/<question_id>/move', methods=['POST'])
@login_required
def move_question(survey_id, question_id):
    db = get_db()
    survey = db.surveys.find_one({'_id': ObjectId(survey_id)})

    if not survey or str(survey['creator_id']) != session['user_id']:
        flash('无权操作', 'error')
        return redirect(url_for('survey.dashboard'))

    direction = request.form.get('direction', 'up')
    questions = list(db.questions.find(
        {'survey_id': survey['_id']}
    ).sort('order', 1))

    qids = [str(q['_id']) for q in questions]
    if question_id not in qids:
        flash('题目不存在', 'error')
        return redirect(url_for('survey.edit', survey_id=survey_id))

    idx = qids.index(question_id)

    if direction == 'up' and idx > 0:
        questions[idx]['order'], questions[idx - 1]['order'] = \
            questions[idx - 1]['order'], questions[idx]['order']
        db.questions.update_one(
            {'_id': questions[idx]['_id']},
            {'$set': {'order': questions[idx]['order']}}
        )
        db.questions.update_one(
            {'_id': questions[idx - 1]['_id']},
            {'$set': {'order': questions[idx - 1]['order']}}
        )
    elif direction == 'down' and idx < len(questions) - 1:
        questions[idx]['order'], questions[idx + 1]['order'] = \
            questions[idx + 1]['order'], questions[idx]['order']
        db.questions.update_one(
            {'_id': questions[idx]['_id']},
            {'$set': {'order': questions[idx]['order']}}
        )
        db.questions.update_one(
            {'_id': questions[idx + 1]['_id']},
            {'$set': {'order': questions[idx + 1]['order']}}
        )

    return redirect(url_for('survey.edit', survey_id=survey_id))


def _build_validation(q_type, form):
    validation = {}

    if q_type == 'multiple_choice':
        min_sel = form.get('min_select', '').strip()
        max_sel = form.get('max_select', '').strip()
        if min_sel:
            validation['min_select'] = int(min_sel)
        if max_sel:
            validation['max_select'] = int(max_sel)

    elif q_type == 'text_fill':
        min_len = form.get('min_length', '').strip()
        max_len = form.get('max_length', '').strip()
        if min_len:
            validation['min_length'] = int(min_len)
        if max_len:
            validation['max_length'] = int(max_len)

    elif q_type == 'number_fill':
        min_val = form.get('min_value', '').strip()
        max_val = form.get('max_value', '').strip()
        must_int = form.get('must_be_integer') == 'on'
        if min_val:
            validation['min_value'] = float(min_val)
        if max_val:
            validation['max_value'] = float(max_val)
        validation['must_be_integer'] = must_int

    return validation


def _build_jump_rules(form, db, survey_id):
    rule_types = form.getlist('jump_condition_type[]')
    rule_values = form.getlist('jump_condition_value[]')
    rule_targets = form.getlist('jump_target[]')

    rules = []
    for i in range(len(rule_types)):
        ct = rule_types[i].strip() if i < len(rule_types) else ''
        cv = rule_values[i].strip() if i < len(rule_values) else ''
        tt = rule_targets[i].strip() if i < len(rule_targets) else ''

        if not ct or not cv or not tt:
            continue

        condition_value = cv
        if ct in ('greater_than', 'less_than', 'equals_num'):
            try:
                condition_value = float(cv)
            except ValueError:
                continue
        elif ct == 'between':
            parts = cv.split(',')
            if len(parts) == 2:
                try:
                    condition_value = [float(p.strip()) for p in parts]
                except ValueError:
                    continue
            else:
                continue

        rules.append({
            'condition_type': ct,
            'condition_value': condition_value,
            'target_question_id': tt
        })

    return rules


def _reorder_questions(db, survey_id):
    questions = list(db.questions.find(
        {'survey_id': survey_id}
    ).sort('order', 1))
    for i, q in enumerate(questions):
        if q['order'] != i + 1:
            db.questions.update_one(
                {'_id': q['_id']},
                {'$set': {'order': i + 1}}
            )


def _clean_jump_rules(db, survey_id, deleted_question_id):
    db.questions.update_many(
        {'survey_id': survey_id},
        {'$pull': {'jump_rules': {'target_question_id': str(deleted_question_id)}}}
    )
