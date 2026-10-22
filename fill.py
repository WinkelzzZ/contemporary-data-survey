from datetime import datetime
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db import get_db

fill_bp = Blueprint('fill', __name__)


@fill_bp.route('/s/<survey_key>')
def fill(survey_key):
    db = get_db()
    survey = db.surveys.find_one({'survey_key': survey_key})

    if not survey:
        flash('问卷不存在', 'error')
        return redirect(url_for('auth.login'))

    if survey['status'] == 'draft':
        flash('该问卷尚未发布', 'error')
        return redirect(url_for('auth.login'))

    if survey['status'] == 'closed':
        flash('该问卷已关闭', 'error')
        return redirect(url_for('auth.login'))

    if survey.get('deadline') and datetime.now() > survey['deadline']:
        flash('该问卷已过截止时间', 'error')
        return redirect(url_for('auth.login'))

    if survey.get('max_responses') is not None:
        current_count = db.responses.count_documents({'survey_id': survey['_id']})
        if current_count >= survey['max_responses']:
            flash('该问卷已达到最大回复数量限制', 'error')
            return redirect(url_for('auth.login'))

    if not survey['allow_anonymous'] and 'user_id' not in session:
        flash('该问卷需要登录后才能填写', 'error')
        session['next_url'] = request.url
        return redirect(url_for('auth.login'))

    questions = list(db.questions.find(
        {'survey_id': survey['_id']}
    ).sort('order', 1))

    questions_data = []
    for q in questions:
        qd = {
            'id': str(q['_id']),
            'order': q['order'],
            'type': q['type'],
            'title': q['title'],
            'required': q.get('required', False),
            'options': q.get('options', []),
            'validation': q.get('validation', {}),
            'jump_rules': q.get('jump_rules', [])
        }
        for rule in qd['jump_rules']:
            rule['target_question_id'] = rule['target_question_id']
        questions_data.append(qd)

    return render_template('fill_survey.html',
                           survey=survey,
                           questions=questions_data)


@fill_bp.route('/s/<survey_key>/submit', methods=['POST'])
def submit(survey_key):
    db = get_db()
    survey = db.surveys.find_one({'survey_key': survey_key})

    if not survey:
        flash('问卷不存在', 'error')
        return redirect(url_for('auth.login'))

    if survey['status'] != 'published':
        flash('该问卷当前不可填写', 'error')
        return redirect(url_for('auth.login'))

    if survey.get('deadline') and datetime.now() > survey['deadline']:
        flash('该问卷已过截止时间', 'error')
        return redirect(url_for('auth.login'))

    if survey.get('max_responses') is not None:
        current_count = db.responses.count_documents({'survey_id': survey['_id']})
        if current_count >= survey['max_responses']:
            flash('该问卷已达到最大回复数量限制', 'error')
            return redirect(url_for('auth.login'))

    if not survey['allow_anonymous'] and 'user_id' not in session:
        flash('该问卷需要登录后才能填写', 'error')
        session['next_url'] = request.url
        return redirect(url_for('auth.login'))

    questions = list(db.questions.find(
        {'survey_id': survey['_id']}
    ).sort('order', 1))

    answers = []
    errors = []

    visible_ids_str = request.form.get('visible_questions', '').strip()
    if visible_ids_str:
        visible_ids = [v.strip() for v in visible_ids_str.split(',') if v.strip()]
    else:
        visible_ids = [str(q['_id']) for q in questions]

    for q in questions:
        qid = str(q['_id'])

        if visible_ids and qid not in visible_ids:
            continue

        q_key = f'q_{qid}'
        raw_value = request.form.get(q_key, '').strip()
        raw_values = request.form.getlist(f'{q_key}[]')

        answer_value = None
        if q['type'] == 'single_choice':
            answer_value = raw_value
        elif q['type'] == 'multiple_choice':
            answer_value = raw_values
        elif q['type'] in ('text_fill', 'number_fill'):
            answer_value = raw_value

        err = _validate_answer(q, answer_value)
        if err:
            errors.append(f'第{q["order"]}题：{err}')
        else:
            answers.append({
                'question_id': q['_id'],
                'question_order': q['order'],
                'value': answer_value
            })

    if errors:
        for e in errors:
            flash(e, 'error')
        questions_data = []
        for q in questions:
            qd = {
                'id': str(q['_id']),
                'order': q['order'],
                'type': q['type'],
                'title': q['title'],
                'required': q.get('required', False),
                'options': q.get('options', []),
                'validation': q.get('validation', {}),
                'jump_rules': q.get('jump_rules', [])
            }
            questions_data.append(qd)
        return render_template('fill_survey.html',
                               survey=survey,
                               questions=questions_data)

    user_id = None
    if not survey['allow_anonymous'] and 'user_id' in session:
        user_id = ObjectId(session['user_id'])
    elif 'user_id' in session:
        user_id = ObjectId(session['user_id'])

    completion_seconds = request.form.get('completion_seconds', '0').strip()
    try:
        completion_seconds = int(completion_seconds)
    except (ValueError, TypeError):
        completion_seconds = 0

    db.responses.insert_one({
        'survey_id': survey['_id'],
        'user_id': user_id,
        'answers': answers,
        'submitted_at': datetime.now(),
        'completion_seconds': completion_seconds
    })

    flash('问卷提交成功，感谢您的参与！', 'success')
    return redirect(url_for('fill.thank_you', survey_key=survey_key))


@fill_bp.route('/s/<survey_key>/thanks')
def thank_you(survey_key):
    db = get_db()
    survey = db.surveys.find_one({'survey_key': survey_key})
    return render_template('thank_you.html', survey=survey)


def _validate_answer(question, value):
    q_type = question['type']
    validation = question.get('validation', {})
    required = question.get('required', False)

    if q_type == 'single_choice':
        if required and not value:
            return '此题为必答题'
        if value and question.get('options') and value not in question['options']:
            return '选择了无效的选项'

    elif q_type == 'multiple_choice':
        if not isinstance(value, list):
            value = [value] if value else []

        if required and len(value) == 0:
            return '此题为必答题'

        if len(value) > 0 and question.get('options'):
            for v in value:
                if v not in question['options']:
                    return f'选择了无效的选项：{v}'

        min_sel = validation.get('min_select')
        max_sel = validation.get('max_select')

        if min_sel and len(value) < min_sel:
            return f'至少需要选择{min_sel}个选项'
        if max_sel and len(value) > max_sel:
            return f'最多只能选择{max_sel}个选项'

    elif q_type == 'text_fill':
        if required and not value:
            return '此题为必答题'

        if value:
            min_len = validation.get('min_length')
            max_len = validation.get('max_length')
            if min_len and len(value) < min_len:
                return f'输入内容不能少于{min_len}个字符'
            if max_len and len(value) > max_len:
                return f'输入内容不能超过{max_len}个字符'

    elif q_type == 'number_fill':
        if required and not value:
            return '此题为必答题'

        if value:
            try:
                num = float(value)
            except ValueError:
                return '请输入有效的数字'

            must_int = validation.get('must_be_integer', False)
            if must_int and num != int(num):
                return '必须输入整数'

            min_val = validation.get('min_value')
            max_val = validation.get('max_value')
            if min_val is not None and num < min_val:
                return f'数字不能小于{min_val}'
            if max_val is not None and num > max_val:
                return f'数字不能大于{max_val}'

    return None
