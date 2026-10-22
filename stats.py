from bson import ObjectId
from flask import Blueprint, render_template, session, flash, redirect, url_for
from db import get_db
from auth import login_required

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/survey/<survey_id>/stats')
@login_required
def survey_stats(survey_id):
    db = get_db()
    survey = db.surveys.find_one({'_id': ObjectId(survey_id)})

    if not survey:
        flash('问卷不存在', 'error')
        return redirect(url_for('survey.dashboard'))

    if str(survey['creator_id']) != session['user_id']:
        flash('无权查看该问卷的统计', 'error')
        return redirect(url_for('survey.dashboard'))

    questions = list(db.questions.find(
        {'survey_id': survey['_id']}
    ).sort('order', 1))

    responses = list(db.responses.find({'survey_id': survey['_id']}))
    total_responses = len(responses)

    time_stats = _compute_time_stats(responses)

    stats = []
    for q in questions:
        q_stat = _compute_question_stats(q, responses)
        q_stat['order'] = q['order']
        q_stat['title'] = q['title']
        q_stat['type'] = q['type']
        q_stat['options'] = q.get('options', [])
        stats.append(q_stat)

    return render_template('survey_stats.html',
                           survey=survey,
                           stats=stats,
                           total_responses=total_responses,
                           time_stats=time_stats)


@stats_bp.route('/survey/<survey_id>/stats/question/<question_id>')
@login_required
def question_stats(survey_id, question_id):
    db = get_db()
    survey = db.surveys.find_one({'_id': ObjectId(survey_id)})

    if not survey or str(survey['creator_id']) != session['user_id']:
        flash('无权查看', 'error')
        return redirect(url_for('survey.dashboard'))

    question = db.questions.find_one({
        '_id': ObjectId(question_id),
        'survey_id': survey['_id']
    })
    if not question:
        flash('题目不存在', 'error')
        return redirect(url_for('stats.survey_stats', survey_id=survey_id))

    responses = list(db.responses.find({'survey_id': survey['_id']}))
    q_stat = _compute_question_stats(question, responses)
    q_stat['order'] = question['order']
    q_stat['title'] = question['title']
    q_stat['type'] = question['type']
    q_stat['options'] = question.get('options', [])

    return render_template('question_stats.html',
                           survey=survey,
                           stat=q_stat,
                           total_responses=len(responses))


def _compute_question_stats(question, responses):
    q_type = question['type']
    qid = question['_id']

    if q_type == 'single_choice':
        option_counts = {}
        for opt in question.get('options', []):
            option_counts[opt] = 0

        answered = 0
        for resp in responses:
            for ans in resp.get('answers', []):
                if ans['question_id'] == qid:
                    answered += 1
                    val = ans.get('value', '')
                    if val in option_counts:
                        option_counts[val] += 1
                    break

        return {
            'option_counts': option_counts,
            'answered': answered,
            'total': len(responses)
        }

    elif q_type == 'multiple_choice':
        option_counts = {}
        for opt in question.get('options', []):
            option_counts[opt] = 0

        answered = 0
        for resp in responses:
            for ans in resp.get('answers', []):
                if ans['question_id'] == qid:
                    answered += 1
                    values = ans.get('value', [])
                    if isinstance(values, list):
                        for v in values:
                            if v in option_counts:
                                option_counts[v] += 1
                    break

        return {
            'option_counts': option_counts,
            'answered': answered,
            'total': len(responses)
        }

    elif q_type == 'text_fill':
        texts = []
        answered = 0
        for resp in responses:
            for ans in resp.get('answers', []):
                if ans['question_id'] == qid:
                    answered += 1
                    val = ans.get('value', '')
                    if val:
                        texts.append(val)
                    break

        return {
            'texts': texts,
            'answered': answered,
            'total': len(responses)
        }

    elif q_type == 'number_fill':
        numbers = []
        answered = 0
        for resp in responses:
            for ans in resp.get('answers', []):
                if ans['question_id'] == qid:
                    answered += 1
                    val = ans.get('value', '')
                    if val:
                        try:
                            numbers.append(float(val))
                        except (ValueError, TypeError):
                            pass
                    break

        result = {
            'numbers': numbers,
            'answered': answered,
            'total': len(responses)
        }

        if numbers:
            result['average'] = sum(numbers) / len(numbers)
            result['min'] = min(numbers)
            result['max'] = max(numbers)
        else:
            result['average'] = 0
            result['min'] = 0
            result['max'] = 0

        return result

    return {'answered': 0, 'total': len(responses)}


def _compute_time_stats(responses):
    times = []
    for resp in responses:
        secs = resp.get('completion_seconds')
        if secs is not None:
            try:
                times.append(int(secs))
            except (ValueError, TypeError):
                pass

    if not times:
        return {'has_data': False, 'average': 0, 'min': 0, 'max': 0}

    avg = sum(times) / len(times)
    return {
        'has_data': True,
        'average': avg,
        'average_display': _format_duration(avg),
        'min': min(times),
        'min_display': _format_duration(min(times)),
        'max': max(times),
        'max_display': _format_duration(max(times)),
        'count': len(times)
    }


def _format_duration(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f'{seconds}秒'
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f'{minutes}分{secs}秒' if secs else f'{minutes}分钟'
    hours = minutes // 60
    mins = minutes % 60
    return f'{hours}小时{mins}分' if mins else f'{hours}小时'
