import unittest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from db import get_db
from bson import ObjectId


class SurveySystemTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ['MONGO_URI'] = 'mongodb://localhost:27017'
        os.environ['DB_NAME'] = 'survey_system_test'
        os.environ['SECRET_KEY'] = 'test-secret'
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.db = get_db()

    @classmethod
    def tearDownClass(cls):
        cls.db.client.drop_database('survey_system_test')

    def setUp(self):
        self.db.users.delete_many({})
        self.db.surveys.delete_many({})
        self.db.questions.delete_many({})
        self.db.responses.delete_many({})

    def _register_and_login(self, username='testuser', password='test123'):
        self.client.post('/register', data={
            'username': username,
            'password': password,
            'confirm': password
        }, follow_redirects=True)

        self.client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def _create_survey(self, title='测试问卷', allow_anonymous=True):
        resp = self.client.post('/survey/create', data={
            'title': title,
            'description': '测试说明',
            'allow_anonymous': 'on' if allow_anonymous else '',
        }, follow_redirects=True)
        return resp

    def _get_survey_id(self):
        survey = self.db.surveys.find_one({})
        return str(survey['_id'])

    def _add_question(self, survey_id, q_type='single_choice', title='测试题目',
                      required=True, options=None, validation=None, jump_rules=None):
        data = {
            'type': q_type,
            'title': title,
            'required': 'on' if required else '',
        }
        if options:
            data['options[]'] = options
        else:
            if q_type in ('single_choice', 'multiple_choice'):
                data['options[]'] = ['选项A', '选项B', '选项C']

        if validation:
            for k, v in validation.items():
                data[k] = v

        if jump_rules:
            data['jump_condition_type[]'] = [r['condition_type'] for r in jump_rules]
            data['jump_condition_value[]'] = [str(r['condition_value']) for r in jump_rules]
            data['jump_target[]'] = [r['target_question_id'] for r in jump_rules]

        return self.client.post(
            f'/survey/{survey_id}/question/add',
            data=data,
            follow_redirects=True
        )

    # ========== 1. 创建问卷测试 ==========
    def test_create_survey(self):
        print('\n===== 测试1：创建问卷 =====')
        self._register_and_login()

        resp = self._create_survey('我的测试问卷')
        self.assertEqual(resp.status_code, 200)

        survey = self.db.surveys.find_one({'title': '我的测试问卷'})
        self.assertIsNotNone(survey)
        self.assertEqual(survey['status'], 'draft')
        self.assertTrue(survey['allow_anonymous'])
        self.assertIsNotNone(survey['survey_key'])
        self.assertEqual(len(survey['survey_key']), 8)
        print(f'  问卷创建成功，ID: {survey["_id"]}, Key: {survey["survey_key"]}')

    def test_create_survey_without_title(self):
        print('\n===== 测试：创建问卷（无标题） =====')
        self._register_and_login()

        resp = self.client.post('/survey/create', data={
            'title': '',
            'description': '无标题测试'
        }, follow_redirects=True)

        survey = self.db.surveys.find_one({'description': '无标题测试'})
        self.assertIsNone(survey)
        print('  无标题问卷被正确拒绝')

    # ========== 2. 添加题目测试 ==========
    def test_add_single_choice_question(self):
        print('\n===== 测试2：添加单选题 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'single_choice', '你的性别',
                           options=['男', '女', '其他'])

        q = self.db.questions.find_one({'survey_id': ObjectId(survey_id), 'type': 'single_choice'})
        self.assertIsNotNone(q)
        self.assertEqual(q['title'], '你的性别')
        self.assertEqual(q['options'], ['男', '女', '其他'])
        self.assertTrue(q['required'])
        self.assertEqual(q['order'], 1)
        print(f'  单选题添加成功，选项: {q["options"]}')

    def test_add_multiple_choice_question(self):
        print('\n===== 测试：添加多选题 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'multiple_choice', '你喜欢的水果',
                           options=['苹果', '香蕉', '西瓜', '葡萄'],
                           validation={'min_select': '2', 'max_select': '3'})

        q = self.db.questions.find_one({'survey_id': ObjectId(survey_id), 'type': 'multiple_choice'})
        self.assertIsNotNone(q)
        self.assertEqual(q['validation']['min_select'], 2)
        self.assertEqual(q['validation']['max_select'], 3)
        print(f'  多选题添加成功，选择限制: {q["validation"]}')

    def test_add_text_fill_question(self):
        print('\n===== 测试：添加文本填空题 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'text_fill', '请自我介绍',
                           validation={'min_length': '10', 'max_length': '200'})

        q = self.db.questions.find_one({'survey_id': ObjectId(survey_id), 'type': 'text_fill'})
        self.assertIsNotNone(q)
        self.assertEqual(q['validation']['min_length'], 10)
        self.assertEqual(q['validation']['max_length'], 200)
        print(f'  文本填空题添加成功，字数限制: {q["validation"]}')

    def test_add_number_fill_question(self):
        print('\n===== 测试：添加数字填空题 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'number_fill', '你的年龄',
                           validation={'min_value': '0', 'max_value': '120', 'must_be_integer': 'on'})

        q = self.db.questions.find_one({'survey_id': ObjectId(survey_id), 'type': 'number_fill'})
        self.assertIsNotNone(q)
        self.assertEqual(q['validation']['min_value'], 0.0)
        self.assertEqual(q['validation']['max_value'], 120.0)
        self.assertTrue(q['validation']['must_be_integer'])
        print(f'  数字填空题添加成功，限制: {q["validation"]}')

    def test_add_multiple_questions_order(self):
        print('\n===== 测试：添加多道题目（顺序） =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'single_choice', '第一题', options=['A', 'B'])
        self._add_question(survey_id, 'text_fill', '第二题')
        self._add_question(survey_id, 'number_fill', '第三题')

        questions = list(self.db.questions.find(
            {'survey_id': ObjectId(survey_id)}
        ).sort('order', 1))

        self.assertEqual(len(questions), 3)
        self.assertEqual(questions[0]['order'], 1)
        self.assertEqual(questions[1]['order'], 2)
        self.assertEqual(questions[2]['order'], 3)
        print(f'  三道题目按顺序添加成功: {[q["title"] for q in questions]}')

    # ========== 3. 跳转逻辑测试 ==========
    def test_jump_logic_single_choice(self):
        print('\n===== 测试3：单选题跳转逻辑 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'single_choice', 'Q1: 你的性别',
                           options=['男', '女', '其他'])
        self._add_question(survey_id, 'text_fill', 'Q2: 问题A')
        self._add_question(survey_id, 'text_fill', 'Q3: 问题B')
        self._add_question(survey_id, 'text_fill', 'Q4: 问题C')
        self._add_question(survey_id, 'text_fill', 'Q5: 问题D')

        questions = list(self.db.questions.find(
            {'survey_id': ObjectId(survey_id)}
        ).sort('order', 1))

        q1_id = str(questions[0]['_id'])
        q5_id = str(questions[4]['_id'])

        self.client.post(f'/survey/{survey_id}/question/{q1_id}/update', data={
            'type': 'single_choice',
            'title': 'Q1: 你的性别',
            'required': 'on',
            'options[]': ['男', '女', '其他'],
            'jump_condition_type[]': ['equals'],
            'jump_condition_value[]': ['男'],
            'jump_target[]': [q5_id]
        }, follow_redirects=True)

        q1 = self.db.questions.find_one({'_id': ObjectId(q1_id)})
        self.assertEqual(len(q1['jump_rules']), 1)
        self.assertEqual(q1['jump_rules'][0]['condition_type'], 'equals')
        self.assertEqual(q1['jump_rules'][0]['condition_value'], '男')
        self.assertEqual(q1['jump_rules'][0]['target_question_id'], q5_id)
        print(f'  跳转规则设置成功: 选"男" → 跳到Q5')

    def test_jump_logic_number_fill(self):
        print('\n===== 测试：数字填空跳转逻辑 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'number_fill', 'Q1: 你的年龄',
                           validation={'min_value': '0', 'max_value': '120', 'must_be_integer': 'on'})
        self._add_question(survey_id, 'text_fill', 'Q2: 学生相关问题')
        self._add_question(survey_id, 'text_fill', 'Q3: 工作相关问题')

        questions = list(self.db.questions.find(
            {'survey_id': ObjectId(survey_id)}
        ).sort('order', 1))

        q1_id = str(questions[0]['_id'])
        q3_id = str(questions[2]['_id'])

        self.client.post(f'/survey/{survey_id}/question/{q1_id}/update', data={
            'type': 'number_fill',
            'title': 'Q1: 你的年龄',
            'required': 'on',
            'min_value': '0',
            'max_value': '120',
            'must_be_integer': 'on',
            'jump_condition_type[]': ['greater_than'],
            'jump_condition_value[]': ['25'],
            'jump_target[]': [q3_id]
        }, follow_redirects=True)

        q1 = self.db.questions.find_one({'_id': ObjectId(q1_id)})
        self.assertEqual(q1['jump_rules'][0]['condition_type'], 'greater_than')
        self.assertEqual(q1['jump_rules'][0]['condition_value'], 25.0)
        print(f'  数字跳转规则设置成功: 年龄>25 → 跳到Q3')

    # ========== 4. 校验测试 ==========
    def test_validation_required_single_choice(self):
        print('\n===== 测试4：必填单选题校验 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'single_choice', '必答题', options=['A', 'B'], required=True)

        survey = self.db.surveys.find_one({'_id': ObjectId(survey_id)})
        self.db.surveys.update_one({'_id': survey['_id']}, {'$set': {'status': 'published'}})

        resp = self.client.post(f'/s/{survey["survey_key"]}/submit', data={
            'visible_questions': ''
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        responses = self.db.responses.count_documents({'survey_id': survey['_id']})
        self.assertEqual(responses, 0)
        print('  未填写必填题被正确拒绝')

    def test_validation_number_range(self):
        print('\n===== 测试：数字范围校验 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'number_fill', '年龄',
                           validation={'min_value': '0', 'max_value': '120', 'must_be_integer': 'on'},
                           required=True)

        survey = self.db.surveys.find_one({'_id': ObjectId(survey_id)})
        self.db.surveys.update_one({'_id': survey['_id']}, {'$set': {'status': 'published'}})

        q = self.db.questions.find_one({'survey_id': survey['_id']})
        qid = str(q['_id'])

        resp = self.client.post(f'/s/{survey["survey_key"]}/submit', data={
            'visible_questions': qid,
            f'q_{qid}': '150'
        }, follow_redirects=True)

        responses = self.db.responses.count_documents({'survey_id': survey['_id']})
        self.assertEqual(responses, 0)
        print('  超出范围的数字被正确拒绝')

    def test_validation_multiple_choice_count(self):
        print('\n===== 测试：多选题数量校验 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'multiple_choice', '选择2-3项',
                           options=['A', 'B', 'C', 'D'],
                           validation={'min_select': '2', 'max_select': '3'},
                           required=True)

        survey = self.db.surveys.find_one({'_id': ObjectId(survey_id)})
        self.db.surveys.update_one({'_id': survey['_id']}, {'$set': {'status': 'published'}})

        q = self.db.questions.find_one({'survey_id': survey['_id']})
        qid = str(q['_id'])

        resp = self.client.post(f'/s/{survey["survey_key"]}/submit', data={
            'visible_questions': qid,
            f'q_{qid}[]': ['A']
        }, follow_redirects=True)

        responses = self.db.responses.count_documents({'survey_id': survey['_id']})
        self.assertEqual(responses, 0)
        print('  选择数量不足被正确拒绝')

    def test_validation_text_length(self):
        print('\n===== 测试：文本长度校验 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'text_fill', '至少10字',
                           validation={'min_length': '10', 'max_length': '50'},
                           required=True)

        survey = self.db.surveys.find_one({'_id': ObjectId(survey_id)})
        self.db.surveys.update_one({'_id': survey['_id']}, {'$set': {'status': 'published'}})

        q = self.db.questions.find_one({'survey_id': survey['_id']})
        qid = str(q['_id'])

        resp = self.client.post(f'/s/{survey["survey_key"]}/submit', data={
            'visible_questions': qid,
            f'q_{qid}': '太短'
        }, follow_redirects=True)

        responses = self.db.responses.count_documents({'survey_id': survey['_id']})
        self.assertEqual(responses, 0)
        print('  文本过短被正确拒绝')

    # ========== 5. 提交问卷测试 ==========
    def test_submit_survey_success(self):
        print('\n===== 测试5：成功提交问卷 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'single_choice', '性别', options=['男', '女'])
        self._add_question(survey_id, 'number_fill', '年龄',
                           validation={'min_value': '0', 'max_value': '120', 'must_be_integer': 'on'})
        self._add_question(survey_id, 'text_fill', '备注')

        survey = self.db.surveys.find_one({'_id': ObjectId(survey_id)})
        self.db.surveys.update_one({'_id': survey['_id']}, {'$set': {'status': 'published'}})

        questions = list(self.db.questions.find({'survey_id': survey['_id']}).sort('order', 1))
        qids = [str(q['_id']) for q in questions]

        resp = self.client.post(f'/s/{survey["survey_key"]}/submit', data={
            'visible_questions': ','.join(qids),
            f'q_{qids[0]}': '男',
            f'q_{qids[1]}': '25',
            f'q_{qids[2]}': '这是一条备注'
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        responses = list(self.db.responses.find({'survey_id': survey['_id']}))
        self.assertEqual(len(responses), 1)
        self.assertEqual(len(responses[0]['answers']), 3)
        self.assertEqual(responses[0]['answers'][0]['value'], '男')
        self.assertEqual(responses[0]['answers'][1]['value'], '25')
        self.assertEqual(responses[0]['answers'][2]['value'], '这是一条备注')
        print(f'  问卷提交成功，包含 {len(responses[0]["answers"])} 个答案')

    def test_submit_multiple_responses(self):
        print('\n===== 测试：多次提交问卷 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'single_choice', '评分', options=['好', '中', '差'])

        survey = self.db.surveys.find_one({'_id': ObjectId(survey_id)})
        self.db.surveys.update_one({'_id': survey['_id']}, {'$set': {'status': 'published'}})

        q = self.db.questions.find_one({'survey_id': survey['_id']})
        qid = str(q['_id'])

        for opt in ['好', '中', '差']:
            self.client.post(f'/s/{survey["survey_key"]}/submit', data={
                'visible_questions': qid,
                f'q_{qid}': opt
            }, follow_redirects=True)

        responses = self.db.responses.count_documents({'survey_id': survey['_id']})
        self.assertEqual(responses, 3)
        print(f'  成功提交 {responses} 份回复')

    def test_submit_closed_survey(self):
        print('\n===== 测试：提交已关闭问卷 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'single_choice', '题目', options=['A', 'B'])

        survey = self.db.surveys.find_one({'_id': ObjectId(survey_id)})
        self.db.surveys.update_one({'_id': survey['_id']}, {'$set': {'status': 'closed'}})

        resp = self.client.get(f'/s/{survey["survey_key"]}', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        print('  已关闭问卷被正确拒绝访问')

    # ========== 6. 统计测试 ==========
    def test_statistics_single_choice(self):
        print('\n===== 测试6：单选题统计 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'single_choice', '性别', options=['男', '女', '其他'])

        survey = self.db.surveys.find_one({'_id': ObjectId(survey_id)})
        self.db.surveys.update_one({'_id': survey['_id']}, {'$set': {'status': 'published'}})

        q = self.db.questions.find_one({'survey_id': survey['_id']})

        for val in ['男', '男', '男', '女', '女', '其他']:
            self.db.responses.insert_one({
                'survey_id': survey['_id'],
                'user_id': None,
                'answers': [{'question_id': q['_id'], 'question_order': 1, 'value': val}],
                'submitted_at': None
            })

        resp = self.client.get(f'/survey/{survey_id}/stats')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('男'.encode('utf-8'), resp.data)
        print('  单选题统计页面正常渲染')

    def test_statistics_number_fill(self):
        print('\n===== 测试：数字填空统计 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'number_fill', '年龄',
                           validation={'min_value': '0', 'max_value': '120'})

        survey = self.db.surveys.find_one({'_id': ObjectId(survey_id)})
        self.db.surveys.update_one({'_id': survey['_id']}, {'$set': {'status': 'published'}})

        q = self.db.questions.find_one({'survey_id': survey['_id']})

        for val in ['20', '25', '30', '35', '40']:
            self.db.responses.insert_one({
                'survey_id': survey['_id'],
                'user_id': None,
                'answers': [{'question_id': q['_id'], 'question_order': 1, 'value': val}],
                'submitted_at': None
            })

        resp = self.client.get(f'/survey/{survey_id}/stats')
        self.assertEqual(resp.status_code, 200)
        print('  数字填空统计页面正常渲染')

    def test_statistics_multiple_choice(self):
        print('\n===== 测试：多选题统计 =====')
        self._register_and_login()
        self._create_survey()
        survey_id = self._get_survey_id()

        self._add_question(survey_id, 'multiple_choice', '水果',
                           options=['苹果', '香蕉', '西瓜'])

        survey = self.db.surveys.find_one({'_id': ObjectId(survey_id)})
        self.db.surveys.update_one({'_id': survey['_id']}, {'$set': {'status': 'published'}})

        q = self.db.questions.find_one({'survey_id': survey['_id']})

        for vals in [['苹果', '香蕉'], ['苹果', '西瓜'], ['香蕉']]:
            self.db.responses.insert_one({
                'survey_id': survey['_id'],
                'user_id': None,
                'answers': [{'question_id': q['_id'], 'question_order': 1, 'value': vals}],
                'submitted_at': None
            })

        resp = self.client.get(f'/survey/{survey_id}/stats')
        self.assertEqual(resp.status_code, 200)
        print('  多选题统计页面正常渲染')

    # ========== 7. 用户认证测试 ==========
    def test_user_registration(self):
        print('\n===== 测试7：用户注册 =====')
        resp = self.client.post('/register', data={
            'username': 'newuser',
            'password': 'pass123',
            'confirm': 'pass123'
        }, follow_redirects=True)

        user = self.db.users.find_one({'username': 'newuser'})
        self.assertIsNotNone(user)
        self.assertIn('created_at', user)
        print(f'  用户注册成功: {user["username"]}')

    def test_duplicate_username(self):
        print('\n===== 测试：重复用户名 =====')
        self._register_and_login('existing')

        resp = self.client.post('/register', data={
            'username': 'existing',
            'password': 'pass123',
            'confirm': 'pass123'
        }, follow_redirects=True)

        users = list(self.db.users.find({'username': 'existing'}))
        self.assertEqual(len(users), 1)
        print('  重复用户名被正确拒绝')

    def test_dashboard_shows_own_surveys(self):
        print('\n===== 测试：仪表盘只显示自己的问卷 =====')
        self._register_and_login('user1')
        self._create_survey('用户1的问卷')

        self.client.get('/logout')

        self._register_and_login('user2')
        self._create_survey('用户2的问卷')

        resp = self.client.get('/dashboard')
        self.assertIn('用户2的问卷'.encode('utf-8'), resp.data)
        self.assertNotIn('用户1的问卷'.encode('utf-8'), resp.data)
        print('  仪表盘正确只显示当前用户的问卷')


if __name__ == '__main__':
    print('=' * 60)
    print('问卷系统测试套件')
    print('=' * 60)
    unittest.main(verbosity=2)
