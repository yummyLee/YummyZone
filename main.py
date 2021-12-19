import linecache
import os.path
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import base64
import json
import uuid
import re

from bson import ObjectId
from pymongo import MongoClient
from tornado.options import define, options

define("port", default=80, help="run on the given port", type=int)

MONGODB_DB_URL = os.environ.get('OPENSHIFT_MONGODB_DB_URL') if os.environ.get(
    'OPENSHIFT_MONGODB_DB_URL') else 'mongodb://localhost:27017/'
MONGODB_DB_NAME = os.environ.get('OPENSHIFT_APP_NAME') if os.environ.get('OPENSHIFT_APP_NAME') else 'yummy_zone'

client = MongoClient(MONGODB_DB_URL)
db = client[MONGODB_DB_NAME]


class BaseHandler(tornado.web.RequestHandler):
    def data_received(self, chunk):
        pass

    def get_current_user(self):
        return self.get_secure_cookie("username")

        # def set_current_user(self):
        #     self.set_secure_cookie("")


class LoginHandler(BaseHandler):
    def get(self):
        self.render('login.html')

    def post(self):
        # self.set_secure_cookie("username", self.get_argument("username"))
        username = self.get_argument("username")
        password = self.get_argument("password")
        print("got post, " + username + ", " + password)
        result = db.user.find_one({"username": username, "password": password})
        result_test = db.user.find_one()
        if result_test is not None:
            print(result_test)
        else:
            print("empty user")
        if result is not None:
            self.set_secure_cookie("username", username)
            self.write(json.dumps({
                "loginResponseType": "success",
                "loginResponseTips": "登录成功。。"
            }))
        else:
            self.write(json.dumps({
                "loginResponseType": "failed",
                "loginResponseTips": "用户名或密码错误。。"
            }))


# 处理登出请求
class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("username")
        self.write(json.dumps({
            "logoutResponseType": "success"
        }))


class IndexHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render('index.html', user=self.current_user)


# 处理工具页面的请求
class ToolHandler(BaseHandler):
    def data_received(self, chunk):
        pass

    @tornado.web.authenticated
    def get(self, *args, **kwargs):
        param = self.get_argument("param", None)
        if param is not None:
            if param == "get_articles":
                offset = self.get_argument("offset", None)
                limit = self.get_argument("limit", None)
                if offset is not None and limit is not None:
                    article_class = self.get_argument("article_class", None)
                    if article_class is not None:
                        # 根据偏移量和查询限制数量在数据库中查找
                        results = db.article.tools.find({"articleClass": article_class}).skip(int(offset)).limit(
                            int(limit))
                    else:
                        results = db.article.tools.find().skip(int(offset)).limit(int(limit))
                    articles = []
                    for a in results:
                        a["_id"] = a["_id"].__str__()
                        a["articleContent"] = ""
                        articles.append(a)
                    print(articles)
                    articles = json.dumps(articles)
                    self.write(articles)
            elif param == "article_class":
                results = db.article_class.tools.find()
                article_classes = []
                for r in results:
                    r["_id"] = r["_id"].__str__()
                    article_classes.append(r)
                article_classes = json.dumps(article_classes)
                print(article_classes)
                self.write(article_classes)
            elif param == "get_html":
                self.set_header("Content-Type", "text/html")
                self.render("tools.html", user=self.current_user)
        else:
            self.set_header("Content-Type", "text/html")
            self.render("container.html", user=self.current_user)


# 处理文章页面的请求
class ArticleHandler(BaseHandler):
    def data_received(self, chunk):
        pass

    def get(self, *args, **kwargs):
        param = self.get_argument("param", None)
        if param is not None:
            if param == "get_html":
                article_id = self.get_argument("article_id")
                print("id = " + article_id)
                article = db.article.tools.find_one({"_id": ObjectId(str(article_id))})
                print(article)
                title = article["articleTitle"]
                content = article["articleContent"]
                date = article["articleDate"]
                desription = article["articleDescription"]
                writer = article["articleWriter"]
                article_class = article["articleClass"]
                self.render("article.html", articleTitle=title, articleContent=content, articleDate=date,
                            articleWriter=writer,
                            articleClass=article_class)
        else:
            self.render("container.html", user=self.current_user)


class AddArticleHandler(BaseHandler):
    def data_received(self, chunk):
        pass

    @tornado.web.authenticated
    def get(self, *args, **kwargs):
        print("got request")
        self.set_header("Content-Type", "text/html")
        param = self.get_argument("param", None)
        if param is not None:
            if param == "get_html":
                self.render("add_article.html", user=self.current_user)
        else:
            self.render("container.html", user=self.current_user)

    def post(self, *args, **kwargs):
        data = self.request.body
        data_decode = json.loads(data)
        print(data_decode)

        # 由于上传的数据进行了base64编码，所以这里需要对数据进行解码然后存入数据库
        description = data_decode['articleDescription'] = base64.b64decode(data_decode['articleDescription']).decode(
            "utf-8")
        title = data_decode['articleTitle'] = base64.b64decode(data_decode['articleTitle']).decode("utf-8")

        if db.article.tools.find_one({"articleTitle": title}) is not None:
            self.write(json.dumps({"addArticleResponseType": "error", "addArticleResponseTips": "已存在同名文章。。"}))
            return

        writer = data_decode['articleWriter'] = base64.b64decode(data_decode['articleWriter']).decode("utf-8")
        article_class = data_decode['articleClass'] = base64.b64decode(data_decode['articleClass']).decode("utf-8")
        date = data_decode['articleDate']
        content = data_decode['articleContent'] = base64.b64decode(data_decode['articleContent']).decode("utf-8")
        article_id = db.article.tools.insert(data_decode)
        db.article_class.tools.update({"articleClass": article_class}, {'$inc': {"articleClassCount": 1}}, True)
        # self.render("article.html", articleTitle=title, articleContent=content, articleDate=date,
        # articleWriter=writer, articleClass=article_class)
        self.write(json.dumps({"addArticleResponseType": "success", "addArticleResponseTips": str(article_id)}))


class BusinessHandler(BaseHandler):
    def data_received(self, chunk):
        pass

    @tornado.web.authenticated
    def get(self, *args, **kwargs):

        param = self.get_argument("param", None)
        if param is not None:
            if param == "business_class":
                print("business_class")
                db_collections = db.collection_names()
                print(db_collections)
                businesses = []
                for col_name in db_collections:
                    match_result = re.match(r"LM\.business\..*?", col_name)
                    if match_result:
                        business = col_name.replace("LM.business.", "")
                        results = db.LM.business[business].find()
                        subservices = {}
                        for r in results:
                            r["_id"] = r["_id"].__str__()
                            if subservices.__contains__(r["subService"]):
                                model_type_list = subservices[r["subService"]]
                                model_type_list.append(r["modelType"])
                            else:
                                new = [r["modelType"]]
                                subservices[r["subService"]] = new
                        print("business = " + business)
                        models = []
                        for k in subservices.keys():
                            klist = subservices[k]
                            models.append({"subServiceName": k, "modelTypes": klist})
                        businesses.append({"business": business, "subservices": models})
                self.write(json.dumps(businesses))

            elif param == "get_service_info":
                sub_service_name = self.get_argument("sub_service_name", None)
                model_type = self.get_argument("model_type", None)
                business = self.get_argument("business", None)
                print(sub_service_name)
                print(model_type)
                print(business)
                if business is not None and sub_service_name is not None:
                    results = db.LM.business[business].find_one(
                        {"subService": sub_service_name, "modelType": model_type})
                    results["_id"] = results["_id"].__str__()
                    self.write(results)

            elif param == "get_html":
                self.render("business.html", user=self.current_user)
        else:
            self.render("container.html", user=self.current_user)


class UploadDocHandler(BaseHandler):
    def data_received(self, chunk):
        pass

    @tornado.web.authenticated
    def get(self, *args, **kwargs):

        param = self.get_argument("param", None)
        if param is not None:
            # if param == "business_class":
            pass
        else:
            self.render("upload_doc.html", user=self.current_user)


def read_file(file_name, offset, limit):
    # file_object = open(file_name, 'r', encoding='utf-8')
    file_content = []
    offset = int(offset)
    limit = int(limit)
    count = 0
    with open(file_name, "r", encoding="utf-8")as f:
        for chunk_data in f:
            count += 1
            if offset <= count < offset + limit:
                print(count)
                file_content.append(chunk_data)
            if count >= offset + limit:
                break
    return file_content


def read_big_file(file_name):
    buf_size = 4096
    with open(file_name, 'r', encoding='utf-8') as f:
        while True:
            data = f.read(buf_size)
            if not data:
                break
            yield data


class OpenFileHandler(tornado.web.RequestHandler):
    def data_received(self, chunk):
        pass

    def get(self, *args, **kwargs):
        param = self.get_argument("param", None)
        if param is not None:
            if param == "read":
                file_name = self.get_argument("file_name", None)
                if os.path.isdir(file_name):
                    file_list = os.listdir(file_name)
                    file_list.append("Iflytek-Dir-Sign")
                    self.write(json.dumps(file_list))
                    return
                if file_name is not None:
                    offset = self.get_argument("offset", None)
                    limit = self.get_argument("limit", None)
                    self.write(json.dumps(read_file(file_name, offset, limit)))
            elif param == "download":
                file_name = self.get_argument("file_name", None)
                self.set_header('Content-Type', 'application/octet-stream')
                self.set_header('Content-Disposition', 'attachment; filename=' + file_name)

                for data in read_big_file(file_name):
                    self.write(data)
                self.finish()


def is_lists_inter(list1, list2):
    for item1 in list1:
        for item2 in list2:
            if item1 == item2:
                return True
    return False


def get_content_related_to_category(search_content):
    keywords = search_content.split(" ")
    db_collections = db.collection_names()
    file_list = []
    file_set = set()
    for col_name in db_collections:
        match_result = re.match(r"LM\.business\..*?", col_name)
        if match_result:
            business = col_name.replace("LM.business.", "")
            results = db.LM.business[business].find()
            for r in results:
                categories = r["corpus"]
                if is_lists_inter(keywords, categories):
                    if "useCorpus" in r:
                        for use in r["useCorpus"]:
                            if use not in file_set:
                                is_related = False
                                for k in keywords:
                                    if use.__contains__(k):
                                        is_related = True
                                if is_related:
                                    file_list.append({"corpus_file_name": use, "business_name": business})
                                    file_set.add(use)
                    else:
                        for m_dir in r["corpusPlace"]:
                            dir_file_list = os.listdir(m_dir)
                            for dir_file in dir_file_list:
                                if dir_file not in file_set:
                                    is_related = False
                                    for k in keywords:
                                        if dir_file.__contains__(k):
                                            is_related = True
                                    if is_related:
                                        file_list.append({"corpus_file_name": dir_file, "business_name": business})
                                        file_set.add(dir_file)
    return file_list


class SearchHandler(tornado.web.RequestHandler):
    def data_received(self, chunk):
        pass

    def get(self, *args, **kwargs):
        param = self.get_argument("param", None)
        if param is not None:
            if param == "category":
                search_content = self.get_argument("search_content")
                result = get_content_related_to_category(search_content)
                self.write(json.dumps(result))


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", IndexHandler),
            (r"/login", LoginHandler),
            (r"/logout", LogoutHandler),
            (r"/tools", ToolHandler),
            (r"/article", ArticleHandler),
            (r"/add_article", AddArticleHandler),
            (r"/business", BusinessHandler),
            (r"/upload_doc", UploadDocHandler),
            (r"/file", OpenFileHandler),
            (r"/search", SearchHandler)
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            debug=True,
            autoescape=None,
            xsrf_cookies=False,
            login_url="/login",
            cookie_secret=base64.b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes)
        )
        tornado.web.Application.__init__(self, handlers, **settings)


if __name__ == "__main__":
    tornado.options.parse_command_line()
    server = tornado.httpserver.HTTPServer(Application())
    server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
