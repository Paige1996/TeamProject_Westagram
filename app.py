import werkzeug.middleware.lint
from flask import Flask, render_template, jsonify, request, redirect, url_for
from pymongo import MongoClient
from flask.wrappers import Response
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from uuid import uuid4
import jwt
import hashlib
import re
import os
import certifi

ca = certifi.where()

client = MongoClient('mongodb+srv://test:sparta@cluster0.qjo3f.mongodb.net/Cluster0?retryWrites=true&w=majority', tlsCAFile=ca)
db = client.dbwesta


app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config['UPLOAD_FOLDER'] = "./static/media/"

SECRET_KEY = 'SPARTA'


def valid_token():
    token_receive = request.cookies.get('wetoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return "로그인 시간이 만료되었습니다"
    except jwt.exceptions.DecodeError:
        return "로그인 정보가 존재하지 않습니다."


def email_check(email):
    return bool(db.users.find_one({'email': email}))


@app.route('/mypage', methods=['GET','POST'])
def mypage():
    valid = valid_token()
    if type(valid) == dict:
        if request.method == 'GET':
            target = db.users.find_one({'email': valid['id']})
            my_feeds = list(db.feeds.find({'email': target['email']}))
            my_feeds_num = len(my_feeds)
            return render_template('mypage.html', my_feeds=my_feeds,  my_feeds_num=my_feeds_num, my_name=target['name'], my_nickname=target['nickname'], my_profile_img=target['profile_img'], self_introduce=target['self_introduce'])
        else:
            try:
                file = request.files['file']
                nickname = request.form['nickname']
                self_introduce = request.form['self_introduce']
                img_name = uuid4().hex
                file.save('./static/media/profile_img/' + img_name)
                img_id = '../static/media/profile_img/' + img_name
                db.users.update_one({'email': valid['id']}, {'$set': {'profile_img': img_id, 'nickname': nickname, 'self_introduce': self_introduce}})
                return jsonify({'result': 'success', 'msg':'성공적으로 반영 되었습니다!'})
            except KeyError:
                nickname = request.form['nickname']
                self_introduce = request.form['self_introduce']
                db.users.update_one({'email': valid['id']}, {'$set': {'nickname': nickname, 'self_introduce': self_introduce}})
                return jsonify({'result': 'success', 'msg': '성공적으로 반영 되었습니다!'})
    else:
        return redirect(url_for('login'))


@app.route('/')
def main():
    valid = valid_token()
    if type(valid) == dict:
        feeds = list(db.feeds.find({}, {'_id':False, 'email':False}))
        feeds.reverse()
        users = list(db.users.find({}, {'_id':False}))
        target = db.users.find_one({'email': valid['id']})

        return render_template('index.html', feeds=feeds, users=users, my_profile_img=target['profile_img'], my_nickname=target['nickname'], my_name=target['name'])
    else:
        return redirect(url_for('login'))


@app.route('/api/feeds', methods=['POST'])
def upload_feed():
    valid = valid_token()
    file = request.files['file']
    img_name = uuid4().hex
    desc = request.form['desc']
    email = valid['id']
    target = db.users.find_one({'email': email})
    user_img = target['profile_img']
    file.save('./static/media/feeds/' + img_name)
    img_id = '../static/media/feeds/' + img_name
    all_feeds = list(db.feeds.find({}, {'_id': False}))
    index = len(all_feeds)
    like_list = []
    like = -1
    comment_list = []
    now = datetime.now()
    now_date = now.strftime('%Y-%m-%d %H:%M')
    doc = {'comment_list': comment_list, 'email':email, 'index': index, 'image_id': img_id, 'user_img':user_img, 'desc': desc, 'nickname': target['nickname'], 'like_list': like_list, 'like':like, 'time': now_date}
    db.feeds.insert_one(doc)
    return jsonify({'result': 'success'})


@app.route('/api/comment', methods=['POST'])
def comment():
    valid = valid_token()
    if type(valid) == dict:
        index_receive = request.form['index_give']
        comment = request.form['comment_give']
        target = db.feeds.find_one({'index': int(index_receive)})
        comment_list = target['comment_list']
        email = valid['id']
        target = db.users.find_one({'email': email})
        my_nickname = target['nickname']
        my_comment = {'my_nickname': my_nickname, 'comment': comment}
        comment_list.append(my_comment)
        db.feeds.update_one({'index': int(index_receive)}, {'$set': {'comment_list': comment_list}})
        return jsonify({'result':'success'})
    else:
        return redirect(url_for('/login'))


@app.route('/api/like', methods=['POST'])
def like():
    valid = valid_token()
    if type(valid) == dict:
        index_receive = request.form['index_give']
        target = db.feeds.find_one({'index': int(index_receive)})
        like_list = target['like_list']
        email = valid['id']

        if email not in like_list:
            like_list.append(email)
            db.feeds.update_one({'index': int(index_receive)}, {'$set': {'like_list': like_list}})
            like_count = len(like_list) - 1
            temp = like_list[0]
            target_user = db.users.find_one({'email': temp})
            nickname = target_user['nickname']
            db.feeds.update_one({'index': int(index_receive)}, {'$set': {'like_nickname': nickname}})
            db.feeds.update_one({'index': int(index_receive)}, {'$set': {'like': like_count}})
            return jsonify({'result': 'success', 'msg': '좋아요 완료!'})
        else:
            like_list.remove(email)
            like_count = len(like_list) - 1
            db.feeds.update_one({'index': int(index_receive)}, {'$set': {'like_list': like_list}})
            db.feeds.update_one({'index': int(index_receive)}, {'$set': {'like': like_count}})
            return jsonify({'msg': '좋아요 취소!'})
    else:
        return redirect(url_for('login'))


@app.route('/join', methods=['GET', 'POST'])
def join():
    if request.method == 'GET':
        # 회원가입 화면 이동
        return render_template('join.html')
    else:
        email = request.form['email']
        name = request.form['name']
        nickname = request.form['nickname']
        temp_password = request.form['password']
        password = hashlib.sha256(temp_password.encode('utf-8')).hexdigest()
        profile_img = '../static/media/profile_img/default-user-img.png'
        follow = []
        follower = []
        self_introduce = ''

        #이메일 유효성 검사
        if (re.search('[^a-zA-Z0-9-_.@]+', email) is not None
                or not (9 < len(email) < 26)):
            return jsonify({'result': 'error', 'msg': '휴대폰번호 또는 이메일의 형식을 확인해주세요. 영문과, 숫자, 일부 특수문자(.-_) 사용 가능. 10~25자 길이'})
        # 비밀번호 유효성 검사
        elif (re.search('[^a-zA-Z0-9!@#$%^&*]+', temp_password) is not None or
              not (7 < len(temp_password) < 21) or
              re.search('[0-9]+', temp_password) is None or
              re.search('[a-zA-Z]+', temp_password) is None):
            return jsonify({'result': 'error', 'msg': '비밀번호의 형식을 확인해주세요. 영문과 숫자 필수 포함, 일부 특수문자(!@#$%^&*) 사용 가능. 8~20자 길이'})
        # 빈칸 검사
        elif not (email and name and nickname and temp_password):
            return jsonify({'result': 'error', 'msg': '빈칸을 입력해주세요.'})
        # 중복 이메일 검사
        elif email_check(email):
            return jsonify({'result': 'error', 'msg': '가입된 내역이 있습니다.'})
        doc = {'email':email, 'name':name, 'nickname':nickname, 'password':password, 'profile_img':profile_img, 'follow':follow, 'follower':follower, 'self_introduce':self_introduce}

        db.users.insert_one(doc)

        return jsonify({'result':'success', 'msg':'회원 가입을 축하드립니다!'})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        # 이미 토큰을 가지고 있는 상태에서 login으로 돌아오는 경우 메인으로 강제 귀환
        valid = valid_token()
        if type(valid) == dict:
            return redirect(url_for('main'))
        else:
            return render_template('login.html')
    else:
        email = request.form['email']
        temp_password = request.form['password']
        password = hashlib.sha256(temp_password.encode('utf-8')).hexdigest()

        temp_user = db.users.find_one({'email': email, 'password': password})

        if temp_user is not None:
            payload = {
                'id': email,
                'exp': datetime.utcnow() + timedelta(seconds=60 * 60)
            }
            token = jwt.encode(payload, SECRET_KEY, algorithm='HS256').decode('utf-8')
            return jsonify({'result': 'success', 'token': token})
        else:
            return Response(status=401)


@app.route('/login', methods=['POST'])
def logout():
    return jsonify({'result': 'success'})


if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)