import werkzeug.middleware.lint
from bson import ObjectId
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

SECRET_KEY = 'WESTAGRAM'  #jwt토큰을 만들기위한 서버 지정값 -> 처음에 아무렇게나 써도 상관은없지만 서비스 운영 중간에 바꾸면 혼란을 초래


def valid_token():
    token_receive = request.cookies.get('wetoken')  #login페이지에서 발급해주는 토큰을 받아옴
    try:
        # 인코딩되어 있던 토큰을 decode(원래대로 분해)과정을 시킴으로써 1.유효한 토큰을 가지고있는지 검증  2.payload안에 담겨있는 현재 사용자의 고유정보(email)를 식별
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        return payload  #현재 사용자의 식별 키인 email을 담고있는 payload 반환
    except jwt.ExpiredSignatureError:
        return "로그인 시간이 만료되었습니다"
    except jwt.exceptions.DecodeError:
        return "로그인 정보가 존재하지 않습니다."


def email_check(email):
    # 입력받은 email값을 db에 조회했을때 이미 존재하는 정보인지(중복인지)를 True/False의 형태로 판별해주는 함수
    return bool(db.users.find_one({'email': email}))


@app.route('/mypage/<status>')
def test(status):
    return redirect(url_for('mypage', status=status))


@app.route('/mypage', methods=['GET','POST'])
def mypage():
    valid = valid_token()  #토큰의 유효성 검사
    status = request.args.get('status')
    if type(valid) == dict:  #를 통과하면
        if request.method == 'GET':  #GET 요청이 들어왔을때
            if status is None:
                status = 0
            else:
                status = 1
            target = db.users.find_one({'email': valid['id']})  #mypage를 구성하는데 필요한 유저 정보(내정보)를 찾기 위해 db에 조회
            my_feeds = list(db.feeds.find({'email': target['email']}))  #email을 사용하여 내가 올렸던 모든 피드들을 찾아옴
            my_feeds_num = len(my_feeds)  #내 게시물 수를 표현하기 위한 변수
            temp_favorite_feeds = target['favorite_feeds']  #사용자의 즐겨찾기 피드 리스트 db에서 불러오기
            favorite_feeds = []  #북마크 페이지에서 새로이 피드들을 보여주기위한 임시 리스트변수
            for i in temp_favorite_feeds:  #북마크된 피드 리스트에는 각 피드의 objectID 값만 담겨있기때문에, 해당 피드의 상세 내용을 가져오기위해 일단 리스트에서 id값들을 하나씩 빼온다
                feed = db.feeds.find_one({"_id": ObjectId(f'{i}')})  #그리고 그 ID로 feeds db에서 해당 피드 데이터를 각각 다 불러옴
                favorite_feeds.append(feed)  #찾아온 피드 데이터들을 위의 favorite_feeds에 담아서 화면에 전송한다
            return render_template('mypage.html', my_feeds=my_feeds,  my_feeds_num=my_feeds_num, my_name=target['name'], my_nickname=target['nickname'], my_profile_img=target['profile_img'], self_introduce=target['self_introduce'], favorite_feeds=favorite_feeds, status=status)
        else:  #mypage에서 POST요청이 들어왔을떄
            try:  #아래를 그냥 실행하면, 적절한 파일이 들어오지 않았을때(프로필 이미지 변경을 하지않았을때) 다른 데이터를 변경시에 에러가 나므로 예외처리
                file = request.files['file']  #프로필 변경 부분에서 사용자가 바꾸고자 서버에 전송한 이미지 파일을 받아옴
                nickname = request.form['nickname']  #사용자가 변경하고자 하는 닉네임을 가져옴
                self_introduce = request.form['self_introduce']  #마찬가지로 자기소개 데이터를 받아옴
                img_name = uuid4().hex   #받아온 이미지 이름을 알파벳/숫자만으로 이루어진 랜덤 값으로 변환
                file.save('./static/media/profile_img/' + img_name)  #받아온 프사를 저장할 서버상의 경로
                img_path = '../static/media/profile_img/' + img_name  #저장한 사진의 위치를 html상에서 다시 찾아갈수 있게끔 db에 저장할 경로
                db.users.update_one({'email': valid['id']}, {'$set': {'profile_img': img_path, 'nickname': nickname, 'self_introduce': self_introduce}})  #프로필 변경시에 포함되는 데이터들을 담아 db에 저장
                db.feeds.update_many({'email': valid['id']}, {'$set': {'user_img': img_path, 'nickname': nickname}})  #이전에 내가 작성한 feed들에 담겨있는 내 프로필사진/닉네임 업데이트
                return jsonify({'result': 'success', 'msg':'성공적으로 반영 되었습니다!'})
            except KeyError:  #위에서 프사변경이 이루어지지않으면 None값이 file에 담기면서 keyerror가 발생, 즉 프사를 제외한 나머지값들만 바꾸고자 할때
                nickname = request.form['nickname']  #사용자 닉네임과
                self_introduce = request.form['self_introduce']  #자기소개 부분의 데이터를 가져와서
                db.users.update_one({'email': valid['id']}, {'$set': {'nickname': nickname, 'self_introduce': self_introduce}})  #db에 반영
                return jsonify({'result': 'success', 'msg': '성공적으로 반영 되었습니다!'})
    else:
        return redirect(url_for('login'))  #유효성 검사를 통과하지 못할 시 login 페이지로 강제 귀환


@app.route('/')
def main():
    valid = valid_token()  #login 페이지에서 정상적으로 토큰을 발급받아 왔는지 확인해주는 유효성 검사
    if type(valid) == dict:  #토큰은 딕셔너리형 데이터이기 때문에 이 조건을 통과한다는 것은 유효한 토큰을 가지고 있다는 이야기
        feeds = list(db.feeds.find({}))  #메인페이지에 뿌려줄 모든 피드데이터를 db에서 가져옴
        feeds.reverse()  #보통 html은 데이터가 쌓이면 위에서 아래 방향으로 누적해 나감, 하지만 우리는 최신정보를 가장 먼저 보고싶어하기 때문에 역순으로 바꿔줌
        users = list(db.users.find({}, {'_id':False}))  #main 페이지에서 사용할 유저 데이터(팔로우 추천을 위한)를 모두 조회
        target = db.users.find_one({'email': valid['id']})  #내 프로필 부분을 꾸며주기위해 현재 사용자 데이터를 db에서 조회
        # 현재 필요한 데이터들을 페이지 렌더링과 동시에 반환
        return render_template('index.html', feeds=feeds, users=users, my_profile_img=target['profile_img'], my_nickname=target['nickname'], my_name=target['name'])
    else:
        return redirect(url_for('login'))  #토큰 유효성 검사에 실패하면(정상적인 토큰을 가져오지 못하거나 유효시간이 지난경우) login페이지로 돌려보내기


@app.route('/api/feeds', methods=['POST'])
def upload_feed():
    valid = valid_token()  #토큰의 유효성 검사 -> 아무나 피드 올리면 안되니까 ^_^
    file = request.files['file']  #사용자가 첨부한 이미지를 받아옴
    img_name = uuid4().hex   #일반적으로 사진의 원본 이름은 공백 문자열/특수문자가 섞여 이를 호출시 에러가 나는 경우가 많음. 이를 방지하기 위해 알파벳/숫자의 조합으로 랜덤한 이름을 부여해주는 uuid4메서드를 사용
    desc = request.form['desc']  #사용자가 기입한 사진 설명부분을 받아옴
    email = valid['id']  #지금 피드 업로드하고있는 사용자의 email값을 토큰에서 뜯어내기
    target = db.users.find_one({'email': email})  #사용자의 다른 정보를 더 찾아내기 위해 위에서 얻은 email로 db에 회원정보(내정보) 조회
    file.save('./static/media/feeds/' + img_name)  #이미지 파일을 실제로 저장할 경로 (서버의 media -> feeds폴더에 저장
    img_path = '../static/media/feeds/' + img_name  #실제로 이 이미지를 html상에서 불러오게 만들기 위한 '사진의 경로'를 db에 저장
    like_list = []  #피드에 좋아요를 누른 사람들의 email 목록을 저장하기 위한 리스트 초기화
    first_like_user = ''  #제일 먼저 좋아요를 누른사람의 닉네임을 담기 위한 문자열 초기화
    like_count = 0  #좋아요를 누른 사람의 수 (~님 외 ~명)를 사용하기 위한 정수형 데이터 초기화
    etc_count = 0
    heart = 0
    bookmark = 0
    comment_list = []  #댓글 목록을 담기위한 리스트 초기화
    now = datetime.now()
    now_date = now.strftime('%Y-%m-%d %H:%M')   #작성 시점의 시간을 피드에 같이 표기해 주기위한 변수, 위의 now가 정의되어 있어야 사용가능
    doc = {'email':email, 'image_path': img_path, 'desc': desc, 'user_img':target['profile_img'], 'nickname': target['nickname'], 'comment_list': comment_list, 'like_list': like_list, 'like_count':like_count, 'etc_count':etc_count, 'first_like_user':first_like_user, 'time': now_date, 'heart':heart, 'bookmark':bookmark}
    db.feeds.insert_one(doc)  #위 내용들을 doc 변수에 담아 db에 저장
    return jsonify({'result': 'success'})


@app.route('/api/feeds/delete', methods=['POST'])
def delete_feed():
    valid = valid_token()
    feed_id = request.form['feed_id']
    target_feed = db.feeds.find_one({"_id": ObjectId(f'{feed_id}')})
    owner = target_feed['email']
    if valid['id'] == owner:
        db.feeds.delete_one({"_id": ObjectId(f'{feed_id}')})
        return jsonify({'result':'success', 'msg':'삭제 완료!'})
    else:
        return jsonify({'result':'error', 'msg':'내가 작성한 피드만 삭제할 수 있습니다!'})


@app.route('/api/comment', methods=['POST'])
def comment():
    valid = valid_token()  #유효성 검사를 통해 댓글달기를 이용할 자격이 있는지 확인
    if type(valid) == dict:
        feed_id = request.form['feed_id']  #어떤 피드에 댓글을 달아야 하는지 식별하기 위해 해당 피드의 id값을 가져옴
        comment = request.form['comment_give']  #input창을 통해서 사용자가 입력한 댓글 내용을 받아옴
        target = db.feeds.find_one({"_id": ObjectId(f'{feed_id}')})  #위에서 받아온 id로 어떤 feed에 내용을 삽입할지 db에 조회
        comment_list = target['comment_list']  #댓글을 저장하기 위해 해당 피드의 댓글 리스트를 불러옴
        email = valid['id']  #현재 댓글의 작성자를 식별하기 위해 토큰으로부터 email값을 추출
        temp = db.users.find_one({'email': email})  #댓글 작성자의 정보를 찾기위해 db에서 조회
        my_nickname = temp['nickname']  #댓글과 함께 달릴 내 닉네임을 가져옴
        my_comment = {'email':email, 'my_nickname': my_nickname, 'comment': comment}  #저장할 내 댓글의 정보를 딕셔너리 형태로 담아주기
        comment_list.append(my_comment)  #피드 댓글 리스트에 내 댓글을 저장
        db.feeds.update_one({"_id": ObjectId(f'{feed_id}')}, {'$set': {'comment_list': comment_list}})  #db에 반영
        return jsonify({'result':'success'})
    else:
        return redirect(url_for('login'))


@app.route('/api/like', methods=['POST'])
def like():
    valid = valid_token()  #발급받은 토큰의 유효성 검사 1.사용자가 가지고있는 토큰이 정상적인가?, 2.토큰의 유효기간이 만료되지 않았는가?
    if type(valid) == dict:  #토큰이 검사를 통과한다면 -> 일반적으로 토큰은 payload/secret_key/algorithm 3가지 형태의 데이터를 섞어 담은 딕셔너리 형태
        feed_id = request.form['feed_id']  #좋아요를 누른 피드의 고유 번호(?)를 가져옴, 어떤 피드에 눌렀는지 식별하기 위함
        target = db.feeds.find_one({"_id": ObjectId(f'{feed_id}')})  #방금 정의한 feed_id로 해당 피드를 db에서 조회
        like_list = target['like_list']  #해당 피드의 좋아요 리스트(좋아요를 누른 사람들의 email을 담은 리스트)
        like_count = target['like_count']
        heart = target['heart']
        email = valid['id']  #현재 좋아요를 누른사람의 email

        if email not in like_list:  #내 이메일이 좋아요 리스트 안에 없다면 -> 내가 이 피드에 좋아요를 누른적이 없다면
            like_list.append(email)  #그 리스트에 내 이메일도 넣어달라
            db.feeds.update_one({"_id": ObjectId(f'{feed_id}')}, {'$set': {'like_list': like_list}})  #그리고 그 결과를 db에 반영해 주시오
            temp = like_list[0]  #제일 처음 좋아요를 누른사람을 정의하기 위한 수단. '~님 외 ~명'에서 '~님'을 찾기위함
            target_user = db.users.find_one({'email': temp})  #'~님'이라는 표현에는 해당 사용자의 email보다 보통 닉네임을 집어넣기 때문에 제일 먼저 좋아요를 누른 사용자를 찾기위해 users db에서 조회
            first_like_user = target_user['nickname']  #target_user에서 정의한 유저의 닉네임
            like_count += 1  # '외 ~명'은 위의 target_user를 제외한 숫자이기 때문에 좋아요를 누른사람들의 리스트 길이에서 1을 빼줌
            etc_count = like_count - 1
            heart += 1
            db.feeds.update_one({"_id": ObjectId(f'{feed_id}')}, {'$set': {'first_like_user': first_like_user, 'like_count': like_count, 'etc_count': etc_count, 'heart':heart}})  #위에서 정의한 정보들을 db에 반영
            return jsonify({'result': 'success', 'msg': '좋아요 완료!'})
        else:  #현재 사용자의 이메일이 like_list 안에 있다면 -> 내가 이 피드에 이미 좋아요를 누른적이 있다면
            like_list.remove(email)  #좋아요를 누른 사람들 리스트에서 내 email을 빼달라
            like_count -= 1
            if like_count != 0:
                etc_count = like_count - 1
                heart -= 1
                db.feeds.update_one({"_id": ObjectId(f'{feed_id}')}, {'$set': {'etc_count': etc_count, 'heart': heart}})

            db.feeds.update_one({"_id": ObjectId(f'{feed_id}')}, {'$set': {'like_list': like_list, 'like_count': like_count}})  #변화가 생긴 데이터들을 db에 저장
            return jsonify({'result': 'success', 'msg': '좋아요 취소!'})
    else:
        return redirect(url_for('login'))


@app.route('/api/favorite', methods=['POST'])
def favorite():
    valid = valid_token()  #유효성 검사
    feed_id = request.form['feed_id']  # 북마크 버튼을 누른 피드의 고유id값을 ajax로 불러오기
    target = db.users.find_one({'email': valid['id']})  # 사용자의 다른 정보를 더 찾아내기 위해 위에서 얻은 email로 db에 회원정보(내정보) 조회
    target_feed = db.feeds.find_one({"_id": ObjectId(f'{feed_id}')})
    favorite_feeds = target['favorite_feeds']  #사용자의 즐겨찾은 게시물 리스트 불러오기
    bookmark = target_feed['bookmark']
    if feed_id in favorite_feeds:
        favorite_feeds.remove(feed_id)
        bookmark -= 1
        db.users.update_one({'email': valid['id']}, {'$set': {'favorite_feeds': favorite_feeds}})
        db.feeds.update_one({"_id": ObjectId(f'{feed_id}')}, {'$set': {'bookmark': bookmark}})
        return jsonify({'result':'success', 'msg':'북마크 취소!'})
    else:
        favorite_feeds.append(feed_id)  #사용자의 즐겨찾기 리스트에 방금 받아온 피드의 id를 저장
        bookmark += 1
        db.users.update_one({'email': valid['id']}, {'$set': {'favorite_feeds': favorite_feeds}})  #db에 반영
        db.feeds.update_one({"_id": ObjectId(f'{feed_id}')}, {'$set': {'bookmark': bookmark}})
        return jsonify({'result':'success', 'msg':'북마크 성공!'})


@app.route('/join', methods=['GET', 'POST'])
def join():
    if request.method == 'GET':
        # 회원가입 화면 이동
        return render_template('join.html')
    else:
        email = request.form['email']
        name = request.form['name']
        nickname = request.form['nickname']         #회원가입 페이지에서 사용자가 입력한 이메일/이름/닉네임/비밀번호를 받아옴
        temp_password = request.form['password']
        password = hashlib.sha256(temp_password.encode('utf-8')).hexdigest()  #비밀번호 해시화(암호화)
        profile_img = '../static/media/profile_img/default-user-img.png'  #사용자 기본 프로필 이미지 경로저장
        follow = []  #사용자가 팔로우 하는 사람을 담을 리스트
        follower = []  #사용자를 팔로우 하는 사람을 담을 리스트
        self_introduce = ''  #mypage 자기소개란에 들어갈 데이터 초기화
        favorite_feeds = []

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

        #모든 검사를 통과 시 받아온 4가지 데이터 필드와 기본 프사/자기소개를 담아 DB에 저장
        doc = {'email':email, 'name':name, 'nickname':nickname, 'password':password, 'profile_img':profile_img, 'follow':follow, 'follower':follower, 'self_introduce':self_introduce, 'favorite_feeds':favorite_feeds}
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
            return render_template('login.html') #토큰이 없는 경우 로그인페이지 렌더링
    else:
        email = request.form['email']
        temp_password = request.form['password']
        password = hashlib.sha256(temp_password.encode('utf-8')).hexdigest() #비밀번호 해시화

        temp_user = db.users.find_one({'email': email, 'password': password}) #사용자가 입력한 id/pw를 가지고 db에 같은 정보가 있는지(회원이 맞는지) 조회

        if temp_user is not None: #db에서 회원정보 조회에 성공한 경우
            payload = {
                'id': email, #토큰발급시 이용중인 유저가 어떤 회원인지를 알아볼 수 있게끔 email로 유니크값 부여 (닉네임이나 사진 본명은 바꿀수있어도 email은 변경 못하게 해야 의미가 있음)
                'exp': datetime.utcnow() + timedelta(seconds=60 * 60 * 3) #토큰의 유효시간설정, 발급 시점으로부터 3시간
            }
            token = jwt.encode(payload, SECRET_KEY, algorithm='HS256').decode('utf-8') #서버에서 미리 생성해놓은 secretkey, 암호화 알고리즘, 페이로드(사용자 식별) 3가지를 encode(믹싱)하여 토큰 생성
            return jsonify({'result': 'success', 'token': token}) #위 과정이 성공시 사용자에게 토큰 반환
        else:
            return Response(status=401)


if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)