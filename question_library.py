import uuid
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db
from auth import login_required

question_library_bp = Blueprint('question_library', __name__)


@question_library_bp.route('/question-library')
@login_required
def library():
    db = get_db()
    user_id = ObjectId(session['user_id'])

    templates = list(db.question_templates.find({
        '$or': [
            {'creator_id': user_id},
            {'shared_with': user_id}
        ]
    }).sort('updated_at', -1))

    for t in templates:
        t['creator'] = db.users.find_one({'_id': t['creator_id']}, {'username': 1})
        t['usage_count'] = db.questions.count_documents({'template_id': t['_id']})
        t['is_owner'] = t['creator_id'] == user_id

    return render_template('question_library.html', templates=templates)


@question_library_bp.route('/question-library/create', methods=['POST'])
@login_required
def create_template():
    title = request.form.get('title', '').strip()
    q_type = request.form.get('type', 'text_fill').strip()
    required = request.form.get('required') == 'on'

    if not title:
        flash('题目标题不能为空', 'error')
        return redirect(url_for('question_library.library'))

    options = []
    if q_type in ('single_choice', 'multiple_choice'):
        options_raw = request.form.getlist('options[]')
        options = [opt.strip() for opt in options_raw if opt.strip()]
        if not options:
            flash('选择题至少需要一个选项', 'error')
            return redirect(url_for('question_library.library'))

    validation = {}
    if q_type == 'multiple_choice':
        min_sel = request.form.get('min_select', '').strip()
        max_sel = request.form.get('max_select', '').strip()
        if min_sel:
            validation['min_select'] = int(min_sel)
        if max_sel:
            validation['max_select'] = int(max_sel)
    elif q_type == 'text_fill':
        min_len = request.form.get('min_length', '').strip()
        max_len = request.form.get('max_length', '').strip()
        if min_len:
            validation['min_length'] = int(min_len)
        if max_len:
            validation['max_length'] = int(max_len)
    elif q_type == 'number_fill':
        min_val = request.form.get('min_value', '').strip()
        max_val = request.form.get('max_value', '').strip()
        must_int = request.form.get('must_be_integer') == 'on'
        if min_val:
            validation['min_value'] = float(min_val)
        if max_val:
            validation['max_value'] = float(max_val)
        if must_int:
            validation['must_be_integer'] = True

    db = get_db()
    db.question_templates.insert_one({
        'creator_id': ObjectId(session['user_id']),
        'title': title,
        'type': q_type,
        'options': options,
        'required': required,
        'validation': validation,
        'jump_rules': [],
        'is_shared': False,
        'shared_with': [],
        'version': 1,
        'parent_id': None,
        'created_at': datetime.now(),
        'updated_at': datetime.now()
    })

    flash('题目已添加到题库', 'success')
    return redirect(url_for('question_library.library'))


@question_library_bp.route('/question-library/<template_id>')
@login_required
def view_template(template_id):
    db = get_db()
    template = db.question_templates.find_one({'_id': ObjectId(template_id)})

    if not template:
        flash('题目不存在', 'error')
        return redirect(url_for('question_library.library'))

    user_id = ObjectId(session['user_id'])
    if template['creator_id'] != user_id and user_id not in template.get('shared_with', []):
        flash('无权访问该题目', 'error')
        return redirect(url_for('question_library.library'))

    version_history = list(db.question_templates.find({
        '$or': [
            {'_id': template['_id']},
            {'parent_id': str(template['_id'])}
        ]
    }).sort('version', -1))

    for v in version_history:
        v['creator'] = db.users.find_one({'_id': v['creator_id']}, {'username': 1})

    surveys_using = []
    questions_using = list(db.questions.find({'template_id': template['_id']}))
    for q in questions_using:
        survey = db.surveys.find_one({'_id': q['survey_id']})
        if survey:
            surveys_using.append({
                'survey': survey,
                'question_order': q['order']
            })

    template['creator'] = db.users.find_one({'_id': template['creator_id']}, {'username': 1})
    template['is_owner'] = template['creator_id'] == user_id

    return render_template('view_template.html',
                         template=template,
                         version_history=version_history,
                         surveys_using=surveys_using)


@question_library_bp.route('/question-library/<template_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(template_id):
    db = get_db()
    template = db.question_templates.find_one({'_id': ObjectId(template_id)})

    if not template:
        flash('题目不存在', 'error')
        return redirect(url_for('question_library.library'))

    user_id = ObjectId(session['user_id'])
    if template['creator_id'] != user_id:
        flash('只有题目创建者可以编辑', 'error')
        return redirect(url_for('question_library.view_template', template_id=template_id))

    if request.method == 'GET':
        return render_template('edit_template.html', template=template)

    title = request.form.get('title', '').strip()
    q_type = request.form.get('type', 'text_fill').strip()
    required = request.form.get('required') == 'on'

    if not title:
        flash('题目标题不能为空', 'error')
        return redirect(url_for('question_library.edit_template', template_id=template_id))

    options = []
    if q_type in ('single_choice', 'multiple_choice'):
        options_raw = request.form.getlist('options[]')
        options = [opt.strip() for opt in options_raw if opt.strip()]
        if not options:
            flash('选择题至少需要一个选项', 'error')
            return redirect(url_for('question_library.edit_template', template_id=template_id))

    validation = {}
    if q_type == 'multiple_choice':
        min_sel = request.form.get('min_select', '').strip()
        max_sel = request.form.get('max_select', '').strip()
        if min_sel:
            validation['min_select'] = int(min_sel)
        if max_sel:
            validation['max_select'] = int(max_sel)
    elif q_type == 'text_fill':
        min_len = request.form.get('min_length', '').strip()
        max_len = request.form.get('max_length', '').strip()
        if min_len:
            validation['min_length'] = int(min_len)
        if max_len:
            validation['max_length'] = int(max_len)
    elif q_type == 'number_fill':
        min_val = request.form.get('min_value', '').strip()
        max_val = request.form.get('max_value', '').strip()
        must_int = request.form.get('must_be_integer') == 'on'
        if min_val:
            validation['min_value'] = float(min_val)
        if max_val:
            validation['max_value'] = float(max_val)
        if must_int:
            validation['must_be_integer'] = True

    create_new_version = request.form.get('create_new_version') == 'on'

    if create_new_version:
        new_template = {
            'creator_id': template['creator_id'],
            'title': title,
            'type': q_type,
            'options': options,
            'required': required,
            'validation': validation,
            'jump_rules': template.get('jump_rules', []),
            'is_shared': template['is_shared'],
            'shared_with': template['shared_with'],
            'version': template['version'] + 1,
            'parent_id': str(template['_id']),
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        result = db.question_templates.insert_one(new_template)
        flash(f'已创建新版本 v{new_template["version"]}', 'success')
        return redirect(url_for('question_library.view_template', template_id=str(result.inserted_id)))
    else:
        db.question_templates.update_one(
            {'_id': template['_id']},
            {'$set': {
                'title': title,
                'type': q_type,
                'options': options,
                'required': required,
                'validation': validation,
                'updated_at': datetime.now()
            }}
        )
        flash('题目已更新', 'success')
        return redirect(url_for('question_library.view_template', template_id=template_id))


@question_library_bp.route('/question-library/<template_id>/delete', methods=['POST'])
@login_required
def delete_template(template_id):
    db = get_db()
    template = db.question_templates.find_one({'_id': ObjectId(template_id)})

    if not template:
        flash('题目不存在', 'error')
        return redirect(url_for('question_library.library'))

    if str(template['creator_id']) != session['user_id']:
        flash('只有题目创建者可以删除', 'error')
        return redirect(url_for('question_library.view_template', template_id=template_id))

    usage_count = db.questions.count_documents({'template_id': template['_id']})
    if usage_count > 0:
        flash(f'该题目正在被 {usage_count} 个问卷使用，无法删除', 'error')
        return redirect(url_for('question_library.view_template', template_id=template_id))

    db.question_templates.delete_one({'_id': template['_id']})
    flash('题目已删除', 'success')
    return redirect(url_for('question_library.library'))


@question_library_bp.route('/question-library/<template_id>/share', methods=['POST'])
@login_required
def share_template(template_id):
    db = get_db()
    template = db.question_templates.find_one({'_id': ObjectId(template_id)})

    if not template:
        flash('题目不存在', 'error')
        return redirect(url_for('question_library.library'))

    if str(template['creator_id']) != session['user_id']:
        flash('只有题目创建者可以分享', 'error')
        return redirect(url_for('question_library.view_template', template_id=template_id))

    username = request.form.get('username', '').strip()
    if not username:
        flash('请输入用户名', 'error')
        return redirect(url_for('question_library.view_template', template_id=template_id))

    target_user = db.users.find_one({'username': username})
    if not target_user:
        flash('用户不存在', 'error')
        return redirect(url_for('question_library.view_template', template_id=template_id))

    if target_user['_id'] == template['creator_id']:
        flash('不能分享给自己', 'error')
        return redirect(url_for('question_library.view_template', template_id=template_id))

    if target_user['_id'] in template.get('shared_with', []):
        flash('该用户已有访问权限', 'info')
        return redirect(url_for('question_library.view_template', template_id=template_id))

    db.question_templates.update_one(
        {'_id': template['_id']},
        {
            '$addToSet': {'shared_with': target_user['_id']},
            '$set': {'is_shared': True, 'updated_at': datetime.now()}
        }
    )

    flash(f'已分享给用户 {username}', 'success')
    return redirect(url_for('question_library.view_template', template_id=template_id))


@question_library_bp.route('/question-library/<template_id>/unshare', methods=['POST'])
@login_required
def unshare_template(template_id):
    db = get_db()
    template = db.question_templates.find_one({'_id': ObjectId(template_id)})

    if not template:
        flash('题目不存在', 'error')
        return redirect(url_for('question_library.library'))

    if str(template['creator_id']) != session['user_id']:
        flash('只有题目创建者可以取消分享', 'error')
        return redirect(url_for('question_library.view_template', template_id=template_id))

    user_id_str = request.form.get('user_id', '').strip()
    if not user_id_str:
        flash('无效的用户', 'error')
        return redirect(url_for('question_library.view_template', template_id=template_id))

    db.question_templates.update_one(
        {'_id': template['_id']},
        {
            '$pull': {'shared_with': ObjectId(user_id_str)},
            '$set': {'updated_at': datetime.now()}
        }
    )

    remaining = db.question_templates.count_documents({
        '_id': template['_id'],
        'shared_with': {'$ne': []}
    })
    if remaining == 0:
        db.question_templates.update_one(
            {'_id': template['_id']},
            {'$set': {'is_shared': False}}
        )

    flash('已取消分享', 'success')
    return redirect(url_for('question_library.view_template', template_id=template_id))


@question_library_bp.route('/question-library/<template_id>/stats')
@login_required
def template_stats(template_id):
    db = get_db()
    template = db.question_templates.find_one({'_id': ObjectId(template_id)})

    if not template:
        flash('题目不存在', 'error')
        return redirect(url_for('question_library.library'))

    user_id = ObjectId(session['user_id'])
    if template['creator_id'] != user_id and user_id not in template.get('shared_with', []):
        flash('无权访问该题目', 'error')
        return redirect(url_for('question_library.library'))

    questions_using = list(db.questions.find({'template_id': template['_id']}))
    survey_ids = [q['survey_id'] for q in questions_using]

    all_responses = list(db.responses.find({'survey_id': {'$in': survey_ids}}))

    stats = _compute_cross_survey_stats(template, questions_using, all_responses)

    template['creator'] = db.users.find_one({'_id': template['creator_id']}, {'username': 1})

    return render_template('template_stats.html',
                         template=template,
                         stats=stats,
                         survey_count=len(survey_ids),
                         response_count=len(all_responses))


def _compute_cross_survey_stats(template, questions_using, responses):
    q_type = template['type']

    if q_type == 'single_choice':
        option_counts = {}
        for opt in template.get('options', []):
            option_counts[opt] = 0

        answered = 0
        for resp in responses:
            for q in questions_using:
                for ans in resp.get('answers', []):
                    if ans['question_id'] == q['_id']:
                        value = ans.get('value')
                        if value:
                            answered += 1
                            if value in option_counts:
                                option_counts[value] += 1
                        break

        total = answered
        option_stats = []
        for opt, count in option_counts.items():
            pct = (count / total * 100) if total > 0 else 0
            option_stats.append({
                'option': opt,
                'count': count,
                'percentage': round(pct, 1)
            })

        return {
            'type': 'single_choice',
            'answered': answered,
            'total': total,
            'options': option_stats
        }

    elif q_type == 'multiple_choice':
        option_counts = {}
        for opt in template.get('options', []):
            option_counts[opt] = 0

        answered = 0
        for resp in responses:
            for q in questions_using:
                for ans in resp.get('answers', []):
                    if ans['question_id'] == q['_id']:
                        value = ans.get('value', [])
                        if not isinstance(value, list):
                            value = [value] if value else []
                        if value:
                            answered += 1
                            for v in value:
                                if v in option_counts:
                                    option_counts[v] += 1
                        break

        total = answered
        option_stats = []
        for opt, count in option_counts.items():
            pct = (count / total * 100) if total > 0 else 0
            option_stats.append({
                'option': opt,
                'count': count,
                'percentage': round(pct, 1)
            })

        return {
            'type': 'multiple_choice',
            'answered': answered,
            'total': total,
            'options': option_stats
        }

    elif q_type == 'text_fill':
        text_values = []
        answered = 0

        for resp in responses:
            for q in questions_using:
                for ans in resp.get('answers', []):
                    if ans['question_id'] == q['_id']:
                        value = ans.get('value')
                        if value:
                            answered += 1
                            text_values.append(value)
                        break

        return {
            'type': 'text_fill',
            'answered': answered,
            'total': len(responses),
            'texts': text_values[:100]
        }

    elif q_type == 'number_fill':
        numbers = []
        answered = 0

        for resp in responses:
            for q in questions_using:
                for ans in resp.get('answers', []):
                    if ans['question_id'] == q['_id']:
                        value = ans.get('value')
                        if value is not None and value != '':
                            try:
                                num = float(value)
                                numbers.append(num)
                                answered += 1
                            except (ValueError, TypeError):
                                pass
                        break

        if not numbers:
            return {
                'type': 'number_fill',
                'answered': 0,
                'total': len(responses),
                'average': 0,
                'min': 0,
                'max': 0,
                'numbers': []
            }

        avg = sum(numbers) / len(numbers)
        must_int = template.get('validation', {}).get('must_be_integer', False)

        return {
            'type': 'number_fill',
            'answered': answered,
            'total': len(responses),
            'average': int(avg) if must_int else round(avg, 2),
            'min': int(min(numbers)) if must_int else min(numbers),
            'max': int(max(numbers)) if must_int else max(numbers),
            'numbers': numbers[:100]
        }

    return {'type': q_type, 'answered': 0, 'total': 0}
