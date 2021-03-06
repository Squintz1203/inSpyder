# encoding="utf-8"
import requests
import re
import json
import time
import random
from orm.sql import manager


class inSpyder(object):
    def __init__(self, themes=[]):
        print("Starting...")
        print("pre-compiling regex patterns...")
        self.patern_CLC_js = re.compile(
            r'/static/bundles/es6/ConsumerLibCommons\.js/(.*?)\.js')
        self.patern_X_IG_App_ID = re.compile(
            r"e\.instagramWebDesktopFBAppId='(.*?)'")
        self.patern_PPC_js = re.compile(
            r'/static/bundles/es6/ProfilePageContainer\.js/(.*?)\.js')
        self.patern_queryId = re.compile(r'l.pagination},queryId:"(.*?)"')
        self.patern_sharedData = re.compile(
            r'window\._sharedData(.*?);</script>')
        print("Connecting to the datatbase...")
        self.master = manager(
            "postgresql://inspyder:No996icu@127.0.0.1:5432/insdata")
        self.user_list = []
        self.user = None
        self.id = ""
        self.biography = ""
        self.posts = 0
        self.following = 0
        self.followers = 0
        self.rt = []
        self.curr_page = []
        self.insIndex = "https://www.instagram.com"
        self.X_IG_App_ID = ""
        self.X_Instagram_AJAX = ""
        self.X_CSRToken = ""
        self.has_next_page = False
        self.next_page_query_hash = ""
        self.end_curr = ""
        self.X_Requested_With = "XMLHttpRequest"
        self.sharedHeader = {
            "Cache-Control": "no-cache",
            "User-Agent":
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0",
            "Accept-Language": "zh-CN,zh;q=0.8"
        }
        self.con = requests.Session()
        print("Updating the requests headers...")
        self.con.headers.update(self.sharedHeader)
        # My dev env has some problems that make me unable to set proxy for requests by code.
        # Instead, I use linux env variable via shell like bash to use proxy.
        # self.con.proxies = {
        #    "http": "http://127.0.0.1:8080",
        #    "https": "http://127.0.0.1:8080",
        # }
        print("loading user list by theme words \'{}\':".format(themes))
        rank_token = str(random.random)
        for theme in themes:
            search_query = "context=blended&query=\'{0}\'&rank_token=\'{1}\'&include_reel=true".format(
                theme, rank_token)
            search_rt = self.con.get(self.insIndex +
                                     "/web/search/topsearch/?" + search_query)
            search_json = search_rt.json()
            search_json_user = search_json["users"]
            print("-----------------------")
            print("Here is the user list for key word \'{}\':".format(theme))
            for node in search_json_user:
                if node["user"]["is_private"] is False:
                    valid_user = node["user"]["username"]
                    self.user_list.append(valid_user)
                    print(valid_user)
        print("Ready to run!")

    def load_extra_info(self, body: str):
        print("-----------------------")
        print("Try to load extra vars...")
        # load X-IG-App-ID
        if self.X_IG_App_ID == "":
            matched = self.patern_CLC_js.search(body)
            app_id_uri = matched.group()
            app_id_js = self.con.get(self.insIndex + app_id_uri)
            app_id_js_body = app_id_js.text
            matched = self.patern_X_IG_App_ID.search(app_id_js_body)
            tmp = matched.group()
            tmp = tmp[tmp.index("\'") + 1:tmp.rindex("\'")]
            self.X_IG_App_ID = tmp
            print("X-IG-App-ID: " + self.X_IG_App_ID)
        # load next-page-query-hash
        if self.next_page_query_hash == "":
            matched = self.patern_PPC_js.search(body)
            next_query_hash_uri = matched.group()
            next_query_hash_js = self.con.get(self.insIndex +
                                              next_query_hash_uri)
            next_query_hash_js_body = next_query_hash_js.text
            matched = self.patern_queryId.search(next_query_hash_js_body)
            tmp = matched.group()
            tmp = tmp[tmp.index('\"') + 1:tmp.rindex('\"')]
            self.next_page_query_hash = tmp
            print("next-page-query-hash: " + self.next_page_query_hash)

    def load_first_page(self):
        print("-----------------------")
        print("Attach the {}\'s index".format(self.user))
        userIndex = self.con.get(self.insIndex + "/" + self.user)
        bodyText = userIndex.text
        print("status: " + str(userIndex.status_code))
        self.load_extra_info(bodyText)
        matched = self.patern_sharedData.search(bodyText)
        sharedData = matched.group()
        sharedData = sharedData[sharedData.index("{"):sharedData.rindex(";")]
        config = json.loads(sharedData, encoding='utf-8')
        self.X_Instagram_AJAX = config["rollout_hash"]
        self.X_CSRToken = config["config"]["csrf_token"]
        self.id = config["entry_data"]["ProfilePage"][0]["graphql"]["user"][
            "id"]
        print("load extra vars from shared data:")
        print("X_CSRToken: " + self.X_CSRToken)
        print("X_Instagram_AJAX: " + self.X_Instagram_AJAX)
        self.biography = config["entry_data"]["ProfilePage"][0]["graphql"][
            "user"]["biography"]
        self.posts = config["entry_data"]["ProfilePage"][0]["graphql"]["user"][
            "edge_owner_to_timeline_media"]["count"]
        self.following = config["entry_data"]["ProfilePage"][0]["graphql"][
            "user"]["edge_follow"]["count"]
        self.followers = config["entry_data"]["ProfilePage"][0]["graphql"][
            "user"]["edge_followed_by"]["count"]
        print("-----------------------")
        print("Get user profile:")
        print("用户名: " + self.user)
        print("ID: " + self.id)
        print("简介: " + self.biography)
        print("发帖数: " + str(self.posts))
        print("关注数: " + str(self.following))
        print("被关注数: " + str(self.followers))
        self.has_next_page = config["entry_data"]["ProfilePage"][0]["graphql"][
            "user"]["edge_owner_to_timeline_media"]["page_info"][
                "has_next_page"]
        self.end_curr = config["entry_data"]["ProfilePage"][0]["graphql"][
            "user"]["edge_owner_to_timeline_media"]["page_info"]["end_cursor"]
        self.curr_page = config["entry_data"]["ProfilePage"][0]["graphql"][
            "user"]["edge_owner_to_timeline_media"]["edges"]

    def next_pages(self):
        next_page_url = self.insIndex + '/graphql/query/?'
        self.con.headers.update({"X_Requested_With": self.X_Requested_With})
        while True:
            for node in self.curr_page:
                if node["node"]["is_video"] is False:
                    pic_id = node["node"]["id"]
                    pic_time_stamp = node["node"]["taken_at_timestamp"]
                    pic_stars = node["node"]["edge_media_preview_like"][
                        "count"]
                    pic_comments = node["node"]["edge_media_to_comment"][
                        "count"]
                    pic_url = node["node"]["display_url"]
                    print("-----------------------")
                    print("图片编号: " + pic_id)
                    print("时间戳: " + str(pic_time_stamp))
                    print("点赞数: " + str(pic_stars))
                    print("评论数: " + str(pic_comments))
                    print("图片链接: " + pic_url)
                    self.rt.append({
                        "pic_id": pic_id,
                        "pic_time_stamp": pic_time_stamp,
                        "pic_stars": pic_stars,
                        "pic_comments": pic_comments,
                        "pic_url": pic_url
                    })
            r_delay = random.randint(0, 2)
            time.sleep(1 + r_delay)
            if self.has_next_page is True:
                param = 'query_hash={0}&variables={{\"id\":\"{1}\",\"first\":12,\"after\":\"{2}\"}}'.format(
                    self.next_page_query_hash, self.id, self.end_curr)
                next_page = self.con.get(next_page_url + param)
                next_json = next_page.json()
                self.has_next_page = next_json["data"]["user"][
                    "edge_owner_to_timeline_media"]["page_info"][
                        "has_next_page"]
                self.end_curr = next_json["data"]["user"][
                    "edge_owner_to_timeline_media"]["page_info"]["end_cursor"]
                self.curr_page = next_json["data"]["user"][
                    "edge_owner_to_timeline_media"]["edges"]
            else:
                break
        print("-----------------------")
        print("Done!")

    def run(self):
        for curr_user in self.user_list:
            self.user = curr_user
            self.load_first_page()
            self.next_pages()
            self.master.update_one_user_data({
                "uid": self.id,
                "username": self.user,
                "biography": self.biography,
                "posts": self.posts,
                "following": self.following,
                "followers": self.followers,
                "blogs": self.rt
            })
            r_delay = random.randint(0, 2)
            time.sleep(1 + r_delay)
        self.con.close()
        self.master.close()


if __name__ == "__main__":
    rt_list = []
    with open("themes.json") as theme_list:
        target = json.load(theme_list)
        themes = target["themes"]
        test = inSpyder(themes)
        test.run()
