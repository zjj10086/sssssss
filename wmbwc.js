/*
------------------------------------------
@Date: 2025.07.07
@Description: 歪麦霸王餐
------------------------------------------
脚本兼容：Surge、QuantumultX、Loon、Shadowrocket、Node.js
只测试过QuantumultX，其它环境请自行尝试

@Description:
脚本兼容：Surge、QuantumultX、Loon、Shadowrocket，不支持青龙

重写：打开app，进入我的页面。

变量：wmbwc_data 格式：[{"userId":"userId","token":"token","userName":"userName"},{"userId":"userId","token":"token","userName":"userName"}]

[rewrite_local]
^https:\/\/wmapp-api\.waimaimingtang\.com\/api\/api\/v2\/user\/api_user_info_one url script-request-body https://gist.githubusercontent.com/Sliverkiss/49a9ffb2169a2becc33bf4fdbf6eb99a/raw/wmbwc.js

[MITM]
hostname = wmapp-api.waimaimingtang.com

⚠️【免责声明】
------------------------------------------
1、此脚本仅用于学习研究，不保证其合法性、准确性、有效性，请根据情况自行判断，本人对此不承担任何保证责任。
2、由于此脚本仅用于学习研究，您必须在下载后 24 小时内将所有内容从您的计算机或手机或任何存储设备中完全删除，若违反规定引起任何事件本人对此均不负责。
3、请勿将此脚本用于任何商业或非法目的，若违反规定请自行对此负责。
4、此脚本涉及应用与本人无关，本人对因此引起的任何隐私泄漏或其他后果不承担任何责任。
5、本人对任何脚本引发的问题概不负责，包括但不限于由脚本错误引起的任何损失和损害。
6、如果任何单位或个人认为此脚本可能涉嫌侵犯其权利，应及时通知并提供身份证明，所有权证明，我们将在收到认证文件确认后删除此脚本。
7、所有直接或间接使用、查看此脚本的人均应该仔细阅读此声明。本人保留随时更改或补充此声明的权利。一旦您使用或复制了此脚本，即视为您已接受此免责声明。
*/
const $ = new Env("歪麦霸王餐");
//notify
const notify = $.isNode() ? require('./sendNotify') : '';
const ckName = "wmbwc_data";
let userCookie = $.toObj($.isNode() ? process.env[ckName] : $.getdata(ckName)) || [];
//用户多账号配置
$.userIdx = 0, $.userList = [], $.notifyMsg = [];
//成功个数
$.succCount = 0;
//debug
$.is_debug = ($.isNode() ? process.env.IS_DEDUG : $.getdata('is_debug')) || 'false';
// 支付密码
$.payPwd = "";
//------------------------------------------
async function main() {
    for (let user of $.userList) {
        $.log(`\n------------- 账号${user.index} -------------\n`)
        //$.notifyMsg = [], $.title = "";
        try {
            await user?.getUserInfo();
            if (user.ckStatus) {
                // 饭票任务
                await user.signin();
                for (let i = 1; i <= 6; i++) {
                    let token = await user.getVideoToken();
                    let taskResult = await user.finishTask(token);
                    if (/上限/.test(taskResult)) break;
                }
                // // 金币任务
                await user?.getNewServiceConfig();
                let pointF = await user.getPoint() ?? {};
                let taskList = await user?.getTaskList();
                // 过滤掉已完成任务
                taskList = taskList.filter(e => e?.nowCount != e?.targetCount)
                for (item of taskList) {
                    // 过滤掉已经完成的任务
                    item.rewardList = item.rewardList.filter(e => e?.rewardStatus != 2);
                    drink: for (let sortItem of item?.rewardList) {
                        //随机等待3秒
                        await $.wait(3e3);
                        item.sort = sortItem?.sort;
                        item.signDate = sortItem.signDate;
                        switch (item?.taskName) {
                            case "完成霸王餐订单":
                            case "邀请好友得麦粒或会员":
                                break drink;
                            case "看视频赚金币":
                            case "歪麦专属优惠券":
                            case "拆红包领金币":
                            case "浏览赚金币":
                                await user?.taskFinish(item);
                                break;
                            default:
                                let res = await user?.taskFinish(item);
                                if (/未到达解锁时间|无效签到日期/.test(res)) break drink;
                                await user?.taskDouble(item);
                                break;
                        }
                    }
                }
                // 兑换麦粒
                await user?.exchangeGrain();
                // 查询实名
                let userReal = await user?.getRealName();
                // 提现 
                if (userReal?.actualName && userReal?.accountBalance >= 2) {
                    await user?.applyWithdraw(userReal);
                }
                // 查询金币
                let pointE = await user.getPoint() ?? {};
                $.notifyMsg.push(`[${user.userName}] 金币:${pointF}${parseInt(pointE) >= parseInt(pointF) ? "+" : ""}${parseInt(pointE) - parseInt(pointF)}`);
                $.succCount++;
            } else {
                $.error(`[${user?.userName}] ck已失效，用户需要去登录`);
                $.notifyMsg.push(`[${user?.userName}] 积分:ck已失效，用户需要去登录`);
            }
        } catch (e) {
            throw e
        }
    }
    $.title = `共${$.userList.length}个账号,成功${$.succCount}个,失败${$.userList.length - 0 - $.succCount}个`
    //notify
    await sendMsg($.notifyMsg.join("\n"), { $media: $.avatar });
}



//用户
class UserInfo {
    constructor(user) {
        //-------------------------- 固定不动区域 ---------------------------------
        this.index = ++$.userIdx;
        this.avatar = user.avatar;
        this.ckStatus = true;
        this.userId = "" || user.userId;
        this.userName = user.userName || this.userId || this.index;
        this.token = "" || user.token || user;
        //-------------------------- 请求封装区域 ---------------------------------
        //请求封装
        this.baseUrl = `https://wmapp-api.waimaimingtang.com`;
        this.headers = {
            "user-agent": "Dart/3.7 (dart:io)",
            "system": "iOS",
            "x-user-agent": "user-agent",
            "appversion": "1.1.154",
            "content-type": "application/json;charset=UTF-8",
            "token": this.token,
            "application": "app",
            "appchannel": "App Store",
            //"host": "wmapp-api.waimaimingtang.com",
            "apiversion": 1,
        };
        //
        return createProxy(this, this.handleError); // 使用 Proxy 包装实例
    }
    //-------------------------- 工具函数区域 ---------------------------------
    // 通用错误处理方法
    handleError(error) {
        this.ckStatus = false;
        $.error(`[${this.userName}] 发生错误：${error.message}`);
    }
    // 通用请求方法
    async fetch(o) {
        const options = typeof o === 'string' ? { url: o } : o;
        const url = new URL(options.url || '', this.baseUrl).href;
        const res = await Request({
            ...options,
            headers: options.headers || this.headers,
            url: url
        });
        debug(res, url.replace(/\/+$/, '').substring(url.lastIndexOf('/') + 1));
        //if (res?.msg && /请重新登录/.test(res.msg)) throw new Error(`登录错误: ${res.msg}`);
        return res;
    }
    //-------------------------- 脚本函数区域 ---------------------------------
    // 签到
    async signin() {
        let timestamp = (new Date).getTime();
        let nonce = randomCode();
        const opts = {
            url: "/api/api/v2/user/api_user_sign_in",
            type: "post",
            dataType: "json",
            headers: {
                ...this.headers,
                "timestamp": timestamp,
                "x-fetch-ts": timestamp,
                "nonce": nonce,
                "sign": encryptSign(timestamp + nonce)
            },
            body: {
                "json": encrypt($.toStr({
                    "userId": this.userId,
                    "userBehavior": "sign_in_v2",
                    "serviceNoStr": "api_user_sign_in"
                }))
            }
        }
        let res = await this.fetch(opts);
        $.info(`[${this.userName}] 签到:${res?.message}`);
    }
    // 完成任务
    async finishTask(token) {
        let timestamp = (new Date).getTime();
        let nonce = randomCode();
        const opts = {
            url: "/api/api/v2/user/api_user_task_finish",
            type: "post",
            dataType: "json",
            headers: {
                ...this.headers,
                "timestamp": timestamp,
                "x-fetch-ts": timestamp,
                "nonce": nonce,
                "sign": encryptSign(timestamp + nonce)
            },
            body: {
                "json": encrypt($.toStr({
                    "serviceNoStr": "api_user_task_finish",
                    "taskKey": "view_video",
                    "userId": this.userId,
                    "token": token
                }))
            }
        }
        let res = await this.fetch(opts);
        $.info(`[${this.userName}] 看视频:${res?.message}`);
        return res?.message;
    }
    // 获取视频token
    async getVideoToken() {
        let timestamp = (new Date).getTime();
        let nonce = randomCode();
        const opts = {
            url: "/api/api/v2/user/api_user_video_task_token",
            type: "post",
            dataType: "json",
            headers: {
                ...this.headers,
                "timestamp": timestamp,
                "x-fetch-ts": timestamp,
                "nonce": nonce,
                "sign": encryptSign(timestamp + nonce)
            },
            body: {
                "json": encrypt($.toStr({
                    "serviceNoStr": "api_user_video_task_token",
                }))
            }
        }
        let res = await this.fetch(opts);
        return decrypt(res?.data) ?? ""
    }
    // 获取用户信息
    async getUserInfo() {
        let timestamp = (new Date).getTime();
        let nonce = randomCode();
        const opts = {
            url: "/api/api/v2/user/api_user_info_one",
            type: "post",
            dataType: "json",
            headers: {
                ...this.headers,
                "timestamp": timestamp,
                "x-fetch-ts": timestamp,
                "nonce": nonce,
                "sign": encryptSign(timestamp + nonce)
            },
            body: {
                "json": encrypt($.toStr({
                    "userId": this.userId,
                    "serviceNoStr": "api_user_info_one",
                    "city": "南宁市"
                }))
            }
        }
        let res = await this.fetch(opts);
        let data = $.toObj(decrypt(res?.data)) ?? {};
        let { phoneNumber, integral } = data;
        this.userName = phoneNumber;
    }

    // 获取aes key配置
    async getNewServiceConfig() {
        // let timestamp = (new Date).getTime();
        // let nonce = randomCode();
        // const opts = {
        //     url: "/api/api/v2/index/newServiceConfig",
        //     type: "post",
        //     dataType: "json",
        //     headers: {
        //         ...this.headers,
        //         "timestamp": timestamp,
        //         "x-fetch-ts": timestamp,
        //         "nonce": nonce,
        //         "sign": encryptSign(timestamp + nonce)
        //     },
        //     body: {
        //         "json": encrypt($.toStr({ "city": "" }))
        //     }
        // }
        // let res = await this.fetch(opts);
        //const { privateKey, publicKey } = $.toObj(decrypt(res?.data)) ?? {};
        // 改为固定key
        let { privateKey, publicKey } = { "newSearchFlag": true, "privateKey": "MIICdwIBADANBgkqhkiG9w0BAQEFAASCAmEwggJdAgEAAoGBAJcDOP6tHa3CyPBkOSs18kKdvwvQ3yniGOrXOiBx4gojn7skzjJZqLlECI7bIXLElADQm82saferyHZegxYdxIKnOM4H0ECH6BmuXlhY7Q6LA85wFAttIYpbJUKfPYQI8Wuz/wm4KurZY1IibemKGzaOeSHhseeSBgno2eNSbXzjAgMBAAECgYAsazE/kBIzwyCxvPkn4aVRvO6t/hE2U5/6q7YYRwcy7kmUlX3lR4Qegol147TR+kqCdtntRHKi/C9pyeELB1R+mf9r34/yZnz8DjQHo7/UmZq3Fqew9p5FtmZq2d+EDWcwhfm8B3NJdBPtNAcuq4PcxzPYcICoW/2xW1M5pWbV4QJBAM4U5SQtOIW+6UXTi75djP9qIqy1WcuFmbugmLRodogkn5MTKph0S6cFoRdR9SCofzQp0jHYuro7PkVr8Wgj3zECQQC7l4BPD88SK+rl4N6WgP/i3AW0RfwWq3yL3Kren3teyVh0+xcp0Lfuw+5fEvEK9AwGkhaXW8zAw4o4c2PjxiBTAkEAkjkHQT0I3vVQBWiNvhwY4F3Jjqv6s8rvAs93qoJ4oC8EPtIZpiTWTQNUgvx3Jp4H69ZEu3OhQmSo0Y8+sfrJ8QJAGe4oM0WJJwbhEmOSARXVySMGutONtAiCT8bx65H5+LE2Q/1NR19tfViiA4xXu17epq3c55Et7VtaKNFydlK1twJBAIFWaFIv0VvQaYv8ykYcb3RDtFKMehhSZ7tGe4WJ1lSGtA9J6f7ZEAOKH3SbOYfRvfT+7pSrQYdYBJvp+SxvSUg=", "newApiFlag": true, "h5PublicKey": "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC+JuPgFj0i+R2+RrKVwgxhFOX4uerf1OT8drIKXPUczbjNIKXpJVAXEb0sVuXe+QLpVf/c8hb2pMH4qFzrx4xfjMsa2J0iu0AKq0kxqOLyIliun0J4bTGjFMESHzgnEZRx3zVWl8VTW2Yau+JsCEkLfoF/hAWBR370z7u2XwRApwIDAQAB", "newDetailFlag": true, "newSignUpFlag": true, "publicKey": "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDc1awKURsvACHORUhbbrebf3xuSy2v2DLO0wUP3Wh9ehWdrq2B3TiwHJpvl7jP2VZNvPjdjFLQ8J+X3KcqierF8RinhfPEhYDWF91BqExMKzg7BJJC+IOiW8OFFKrWRGudWzC9N2Dtm6/WvAyCnB0apEdN385qExv6nXzoVnEuAQIDAQAB" }

        $.PUBLIC_KEY = `-----BEGIN PUBLIC KEY-----\n${publicKey}\n-----END PUBLIC KEY-----`;
        $.PRIVATE_KEY = `-----BEGIN PRIVATE KEY-----\n${privateKey}\n-----END PRIVATE KEY-----`;
        $.info(`[${this.userName}] 加载动态 AES KEY配置成功`);
    }
    // 获取用户信息
    async getPoint() {
        let timestamp = (new Date).getTime();
        let nonce = randomCode();
        let { encryptKey, body: encryptData } = rsaEncrypt({})
        const opts = {
            url: "https://wmapp-api-v2.waimaimingtang.com/api/bwc/waimaimt-web-bwc/user/task/earning/gold/summary",
            type: "post",
            dataType: "form",
            resultType: "all",
            headers: {
                ...this.headers,
                "timestamp": timestamp,
                "x-fetch-ts": timestamp,
                "nonce": nonce,
                "sign": encryptSign(timestamp + nonce),
                "encrypt-key": encryptKey
            },
            body: encryptData
        }
        let { headers, body } = await this.fetch(opts);
        let data = rsaDecrypt(headers['encrypt-key'], body);
        $.info(`[${this.userName}] 当前金币:${data?.data?.availableGold}`)
        return data?.data?.availableGold;
    }
    // 获取任务列表
    async getTaskList() {
        let timestamp = (new Date).getTime();
        let nonce = randomCode();
        let { encryptKey, body: encryptData } = rsaEncrypt({})
        const opts = {
            url: "https://wmapp-api-v2.waimaimingtang.com/api/bwc/waimaimt-web-bwc/user/task/earning/home",
            type: "post",
            dataType: "form",
            resultType: "all",
            headers: {
                ...this.headers,
                "timestamp": timestamp,
                "x-fetch-ts": timestamp,
                "nonce": nonce,
                "sign": encryptSign(timestamp + nonce),
                "encrypt-key": encryptKey
            },
            body: encryptData
        }
        let { headers, body } = await this.fetch(opts);
        let data = rsaDecrypt(headers['encrypt-key'], body);
        return [...data?.data?.signInTaskList, ...data?.data?.moreTaskList];
    }
    // 完成任务
    async taskFinish(item) {
        let timestamp = (new Date).getTime();
        let nonce = randomCode();
        let { encryptKey, body: encryptData } = rsaEncrypt({
            "id": item?.id,
            "sort": item.sort,
            "taskKey": item?.taskKey,
            "taskAwardType": item?.taskAwardType,
            "taskId": item?.id,
            "signDate": item?.signDate
        })
        const opts = {
            url: "https://wmapp-api-v2.waimaimingtang.com/api/bwc/waimaimt-web-bwc/user/task/earning/receive",
            type: "post",
            dataType: "form",
            resultType: "all",
            headers: {
                ...this.headers,
                "timestamp": timestamp,
                "x-fetch-ts": timestamp,
                "nonce": nonce,
                "sign": encryptSign(timestamp + nonce),
                "encrypt-key": encryptKey
            },
            body: encryptData
        }
        let { headers, body } = await this.fetch(opts);
        let data = rsaDecrypt(headers['encrypt-key'], body);
        $.info(`[${this.userName}] 完成[${item?.taskName}]任务:${data?.msg}`)
        return data?.msg;
    }
    // 双倍奖励
    async taskDouble(item) {
        let timestamp = (new Date).getTime();
        let nonce = randomCode();
        let { encryptKey, body: encryptData } = rsaEncrypt({
            "id": item?.id,
            "sort": item?.sort,
            "taskKey": item?.taskKey,
            "taskAwardType": item?.taskAwardType,
            "taskId": item?.id,
            "signDate": item?.signDate
        })
        const opts = {
            url: "https://wmapp-api-v2.waimaimingtang.com/api/bwc/waimaimt-web-bwc/user/task/earning/boost",
            type: "post",
            dataType: "form",
            resultType: "all",
            headers: {
                ...this.headers,
                "timestamp": timestamp,
                "x-fetch-ts": timestamp,
                "nonce": nonce,
                "sign": encryptSign(timestamp + nonce),
                "encrypt-key": encryptKey
            },
            body: encryptData
        }
        let { headers, body } = await this.fetch(opts);
        let data = rsaDecrypt(headers['encrypt-key'], body);
        $.info(`[${this.userName}] 翻倍[${item?.taskName}]奖励:${data?.msg}`)
    }
    // 金币兑换麦粒
    async exchangeGrain() {
        let timestamp = (new Date).getTime();
        let nonce = randomCode();
        //let { encryptKey, body: encryptData } = rsaEncrypt({});
        let { encryptKey, body: encryptData } = {
            encryptKey: "W/cn5+WxpmbggeJazPE3yqd1lA/lqteMZ97PaWzJEEydkQQYlzPgfoB7oyRd8XRVlemt6eaa6eawYu72Q8yJkqd2JjHXR3MHNoTHovs+weiewU+LslqTH/kgX0AFCZTLIMCg9Kksei1/IP58OpEtHbErVR7z28vlMkJgHIfAWdU=",
            body: "IwcbhinCqgYQSFTgkZcer5djcyS67yM4zNIN1lwVSxI="
        }
        const opts = {
            url: "https://wmapp-api-v2.waimaimingtang.com/api/bwc/waimaimt-web-bwc/user/task/earning/exchange_grain",
            type: "post",
            dataType: "form",
            resultType: "all",
            headers: {
                ...this.headers,
                "timestamp": timestamp,
                "x-fetch-ts": timestamp,
                "nonce": nonce,
                "sign": encryptSign(timestamp + nonce),
                "encrypt-key": encryptKey
            },
            body: encryptData
        }
        let { headers, body } = await this.fetch(opts);
        let data = rsaDecrypt(headers['encrypt-key'], body);
        $.info(`[${this.userName}] 兑换麦粒:${data?.msg}`);
    }
    // 歪麦-获取实名
    async getRealName() {
        let timestamp = (new Date).getTime();
        let nonce = randomCode();
        const opts = {
            url: `https://91wmsapp-api.waimaimingtang.com/fission/account/balance/${this.userId}`,
            type: "get",
            dataType: "form",
            headers: {
                ...this.headers,
                "timestamp": timestamp,
                "x-fetch-ts": timestamp,
                "nonce": nonce,
                "sign": encryptSign(timestamp + nonce),
            },
        }
        let res = await this.fetch(opts);
        return res?.data;
    }
    // 小程序微信提现
    async applyWithdraw(item) {
        let timestamp = (new Date).getTime();
        let nonce = randomCode();
        const opts = {
            url: "https://91wmsapp-api.waimaimingtang.com/api/api/v2/overbearfood/account/withdrawal/apply",
            type: "post",
            dataType: "json",
            headers: {
                ...this.headers,
                "timestamp": timestamp,
                "x-fetch-ts": timestamp,
                "nonce": nonce,
                "sign": encryptSign(timestamp + nonce)
            },
            body: {
                "json": encrypt($.toStr({
                    "payPwd": $.payPwd,
                    "type": 1,
                    "userId": this.userId,
                    "withdrawAmount": `${item?.accountBalance}.0`,
                    "withdrawalWay": 2,
                    "userName": item?.actualName
                }))
            }
        }
        let res = await this.fetch(opts);
        $.info(`[${this.userName}] 提现${item?.accountBalance}元:${res.message}`);
    }
    //一言
    async getYiYan() {
        let res = await Request("https://api.vvhan.com/api/ian/rand");
        $.info(`[${this.userName}] 获取一言:${res}`);
        return res;
    }


}

function getRandomId() {
    const min = 10000;
    const max = 3000000;
    // Math.random() 生成 [0, 1) 之间的小数
    // 乘以 (max - min + 1) 后再向下取整，即可得到 [0, max-min] 的整数
    // 最后加上 min，得到 [min, max] 的随机整数
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

// 远程通知
async function getNotice() {
    const urls = [
        "https://fastly.jsdelivr.net/gh/Sliverkiss/GoodNight@main/notice.json",
        "https://fastly.jsdelivr.net/gh/Sliverkiss/GoodNight@main/tip.json"
    ];

    try {
        const responses = await Promise.all(urls.map(url => Request(url)));
        responses.map(result => $.log(result?.notice || "获取通知失败"));
        if (responses[0]?.notice) return true;
    } catch (error) {
        console.log(`❌获取通知时发生错误：${error}`);
    }
}

function maskString(input) {
    try {
        if (input?.length <= 6) {
            return input;  // 如果字符串长度小于等于6，直接返回
        }

        // 获取前三位和后三位
        let start = input.slice(0, 3);
        let end = input.slice(-3);

        // 返回处理后的字符串
        return `${start}****${end}`;
    } catch (e) {
        return input
    }
}

function phone_num(phone_num) { if (phone_num.length == 11) { let data = phone_num.replace(/(\d{3})\d{4}(\d{4})/, "$1****$2"); return data; } else { return phone_num; } }

// 获取Cookie
async function getCookie() {
    try {
        if ($request && $request.method === 'OPTIONS') return;

        let Headers = ObjectKeys2LowerCase($request.headers);
        let Body = $.toObj($request.body);
        console.log(JSON.stringify(Body));
        console.log(decrypt(Body?.json))
        let { userId } = $.toObj(decrypt(Body?.json));

        if (!(Headers?.token && userId)) throw new Error("获取token失败！参数缺失");

        const newData = {
            "userId": userId,
            "token": Headers?.token,
            "userName": userId
        }
        const index = userCookie.findIndex(e => e.userId == newData.userId);

        userCookie[index] ? userCookie[index] = newData : userCookie.push(newData);

        $.setjson(userCookie, ckName);
        $.msg($.name, `🎉账号[${newData?.userName}]更新token成功!`, ``);
    } catch (e) {
        throw e;
    }
}

function randomCode() {
    var length = 16;
    var result = '';

    for (var i = 0; i < length; i++) {
        var digit = Math.floor(Math.random() * 9);
        result += digit.toString();
    }

    return result;
}


function encryptSign(data) {
    var key = $.CryptoJS.enc.Utf8.parse("asdf545asdf4545d");

    var encrypted = $.CryptoJS.AES.encrypt(data, key, {
        mode: $.CryptoJS.mode.ECB,
        padding: $.CryptoJS.pad.Pkcs7
    });

    return encrypted.toString();
}

function generateRandomString(len) {
    const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    let result = "";
    for (let i = 0; i < len; i++) result += chars[Math.floor(Math.random() * chars.length)];
    return result;
}

function decrypt(data) {
    let key = $.CryptoJS.enc.Utf8.parse("jnd674751fh6fkgu");

    let decrypted = $.CryptoJS.AES.decrypt(data, key, {
        mode: $.CryptoJS.mode.ECB,
        padding: $.CryptoJS.pad.Pkcs7
    });

    return decrypted.toString($.CryptoJS.enc.Utf8);
}



function encrypt(data) {
    let key = $.CryptoJS.enc.Utf8.parse("jnd674751fh6fkgu");

    let encrypted = $.CryptoJS.AES.encrypt(data, key, {
        mode: $.CryptoJS.mode.ECB,
        padding: $.CryptoJS.pad.Pkcs7
    });

    return encrypted.toString();
}

function rsaEncrypt(data) {
    // 1. 生成 32 位随机 AES 密钥
    const randomKey = generateRandomString(32);

    // 2. encrypt-key = RSA(Base64(randomKey), publicKey)
    const base64Key = $.CryptoJS.enc.Base64.stringify($.CryptoJS.enc.Utf8.parse(randomKey));
    const encryptor = new ($.Utils.loadJSEncrypt());
    encryptor.setPublicKey($.PUBLIC_KEY);
    const encryptKey = encryptor.encrypt(base64Key);
    if (!encryptKey) throw new Error("RSA 加密失败");

    // 3. body = AES-ECB(JSON.stringify(data), key=randomKey)
    const body = $.CryptoJS.AES.encrypt(
        JSON.stringify(data),
        $.CryptoJS.enc.Utf8.parse(randomKey),
        { mode: $.CryptoJS.mode.ECB, padding: $.CryptoJS.pad.Pkcs7 }
    ).toString();

    return { encryptKey, body, randomKey };
}

function rsaDecrypt(encryptKey, body) {
    // 1. RSA 解密 encrypt-key → Base64(randomKey)
    const encryptor = new ($.Utils.loadJSEncrypt());
    encryptor.setPrivateKey($.PRIVATE_KEY);
    const randomKeyBase64 = encryptor.decrypt(encryptKey);
    if (!randomKeyBase64) throw new Error("RSA 解密 encrypt-key 失败，encrypt-key 可能来自请求方向（需要用 publicKey 配对私钥）");

    // 2. Base64 解码 → randomKey
    const randomKey = $.CryptoJS.enc.Base64.parse(randomKeyBase64).toString($.CryptoJS.enc.Utf8);

    // 3. AES-ECB 解密 body
    const plaintext = $.CryptoJS.AES.decrypt(
        body,
        $.CryptoJS.enc.Utf8.parse(randomKey),
        { mode: $.CryptoJS.mode.ECB, padding: $.CryptoJS.pad.Pkcs7 }
    ).toString($.CryptoJS.enc.Utf8);

    return JSON.parse(plaintext);
}

//加载CryptoJS模块
async function loadCryptoJS() {
    let code = ($.isNode() ? require('crypto-js') : $.getdata('CryptoJS_code')) || '';
    //node环境
    if ($.isNode()) return code;
    //ios环境
    if (code && Object.keys(code).length) {
        console.log(`[INFO] 缓存中存在CryptoJS代码, 跳过下载\n`)
        eval(code)
        return createCryptoJS();
    }
    console.log(`[INFO] 开始下载CryptoJS代码\n`)
    return new Promise(async (resolve) => {
        $.getScript(
            'https://fastly.jsdelivr.net/gh/Sliverkiss/QuantumultX@main/Utils/CryptoJS.min.js'
        ).then((fn) => {
            $.setdata(fn, 'CryptoJS_code')
            eval(fn)
            const CryptoJS = createCryptoJS();
            console.log(`[INFO] CryptoJS加载成功, 请继续\n`)
            resolve(CryptoJS)
        })
    })
}

//加载Jsrsasign模块
async function loadUtils() {
    let code = $.getdata('Utils_Code') || '';
    if (code && Object.keys(code).length) {
        console.log(`✅ ${$.name}: 缓存中存在Utils代码, 跳过下载`)
        eval(code)
        return creatUtils();
    }
    console.log(`🚀 ${$.name}: 开始下载Utils代码`)
    return new Promise(async (resolve) => {
        $.getScript(
            'https://fastly.jsdelivr.net/gh/xzxxn777/Surge@main/Utils/Utils.js'
        ).then((fn) => {
            $.setdata(fn, "Utils_Code")
            eval(fn)
            console.log(`✅ Utils加载成功, 请继续`)
            resolve(creatUtils())
        })
    })
}

//处理node
function getEnvByNode() {
    let ckList = $.toObj(process.env[ckName]);
    if (!ckList) {
        ckList = ckList.split("&");
        ckList = ckList.map(e => {
            const [token, userName] = e.split('#');
            let newData = {
                "userId": token,
                "userName": userName
            }
            return newData
        });
    }
    return ckList;
}

//主程序执行入口
!(async () => {
    $.CryptoJS = await loadCryptoJS();
    $.Utils = await loadUtils();
    if (typeof $request != "undefined") {
        await getCookie();
    } else {

        await checkEnv();
        await main();
    }
})()
    .catch((e) => { $.logErr(e), $.msg($.name, `⛔️ script run error!`, e.message || e) })
    .finally(() => $.done());

/** ---------------------------------固定不动区域----------------------------------------- */
//prettier-ignore
function createProxy(t, n) { return new Proxy(t, { get(t, r) { const c = t[r]; return "function" == typeof c ? async function (...r) { try { return await c.apply(t, r) } catch (r) { n.call(t, r) } } : c } }) }
async function sendMsg(a, e) { a && ($.isNode() ? await notify.sendNotify($.name, a) : $.msg($.name, $.title || "", a, e)) }
function DoubleLog(o) { o && ($.log(`${o}`), $.notifyMsg.push(`${o}`)) };
async function checkEnv() { try { if (!userCookie?.length) throw new Error("no available accounts found"); $.log(`\n[INFO] 检测到 ${userCookie?.length ?? 0} 个账号\n`), $.userList.push(...userCookie.map((o => new UserInfo(o))).filter(Boolean)) } catch (o) { throw o } }
function debug(g, e = "debug") { "true" === $.is_debug && ($.log(`\n-----------${e}------------\n`), $.log("string" == typeof g ? g : $.toStr(g) || `debug error => t=${g}`), $.log(`\n-----------${e}------------\n`)) }
//From xream's ObjectKeys2LowerCase
function ObjectKeys2LowerCase(obj) { return !obj ? {} : Object.fromEntries(Object.entries(obj).map(([k, v]) => [k.toLowerCase(), v])) };
//From sliverkiss's Request
async function Request(t) { "string" == typeof t && (t = { url: t }); try { if (!t?.url) throw new Error("[URL][ERROR] 缺少 url 参数"); let { url: o, type: e, headers: r = {}, body: s, params: a, dataType: n = "form", resultType: u = "data" } = t; const p = e ? e?.toLowerCase() : "body" in t ? "post" : "get", c = o.concat("post" === p ? "?" + $.queryStr(a) : ""), i = t.timeout ? $.isSurge() ? t.timeout / 1e3 : t.timeout : 1e4; "json" === n && (r["Content-Type"] = "application/json;charset=UTF-8"); const y = "string" == typeof s ? s : (s && "form" == n ? $.queryStr(s) : $.toStr(s)), l = { ...t, ...t?.opts ? t.opts : {}, url: c, headers: r, ..."post" === p && { body: y }, ..."get" === p && a && { params: a }, timeout: i }, m = $.http[p.toLowerCase()](l).then((t => "data" == u ? $.toObj(t.body) || t.body : $.toObj(t) || t)).catch((t => $.log(`[${p.toUpperCase()}][ERROR] ${t}\n`))); return Promise.race([new Promise(((t, o) => setTimeout((() => o("当前请求已超时")), i))), m]) } catch (t) { console.log(`[${p.toUpperCase()}][ERROR] ${t}\n`) } }
//jwt parse tool
function parseJwt(t) { const e = t.split("."); if (3 !== e.length) throw new Error("Invalid JWT token"); const a = JSON.parse(o(e[0])), r = JSON.parse(o(e[1])), n = new Date(1e3 * r.exp), p = new Date(parseInt(r.create_date)); return { header: a, payload: r, expDate: g(n), createDate: g(p) }; function o(t) { let e = t.replace(/-/g, "+").replace(/_/g, "/"), a = e.length % 4; a && (e += "=".repeat(4 - a)); const r = atob(e); return decodeURIComponent(escape(r)) } function g(t) { return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")} ${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}:${String(t.getSeconds()).padStart(2, "0")}` } }
//From chavyleung's Env.js
function Env(t, e) { class s { constructor(t) { this.env = t } send(t, e = "GET") { t = "string" == typeof t ? { url: t } : t; let s = this.get; return "POST" === e && (s = this.post), new Promise(((e, i) => { s.call(this, t, ((t, s, o) => { t ? i(t) : e(s) })) })) } get(t) { return this.send.call(this.env, t) } post(t) { return this.send.call(this.env, t, "POST") } } return new class { constructor(t, e) { this.logLevels = { debug: 0, info: 1, warn: 2, error: 3 }, this.logLevelPrefixs = { debug: "[DEBUG] ", info: "[INFO] ", warn: "[WARN] ", error: "[ERROR] " }, this.logLevel = "info", this.name = t, this.http = new s(this), this.data = null, this.dataFile = "box.dat", this.logs = [], this.isMute = !1, this.isNeedRewrite = !1, this.logSeparator = "\n", this.encoding = "utf-8", this.startTime = (new Date).getTime(), Object.assign(this, e), this.log("", `🔔${this.name}, 开始!`) } getEnv() { return "undefined" != typeof $environment && $environment["surge-version"] ? "Surge" : "undefined" != typeof $environment && $environment["stash-version"] ? "Stash" : "undefined" != typeof module && module.exports ? "Node.js" : "undefined" != typeof $task ? "Quantumult X" : "undefined" != typeof $loon ? "Loon" : "undefined" != typeof $rocket ? "Shadowrocket" : void 0 } isNode() { return "Node.js" === this.getEnv() } isQuanX() { return "Quantumult X" === this.getEnv() } isSurge() { return "Surge" === this.getEnv() } isLoon() { return "Loon" === this.getEnv() } isShadowrocket() { return "Shadowrocket" === this.getEnv() } isStash() { return "Stash" === this.getEnv() } toObj(t, e = null) { try { return JSON.parse(t) } catch { return e } } toStr(t, e = null, ...s) { try { return JSON.stringify(t, ...s) } catch { return e } } getjson(t, e) { let s = e; if (this.getdata(t)) try { s = JSON.parse(this.getdata(t)) } catch { } return s } setjson(t, e) { try { return this.setdata(JSON.stringify(t), e) } catch { return !1 } } getScript(t) { return new Promise((e => { this.get({ url: t }, ((t, s, i) => e(i))) })) } runScript(t, e) { return new Promise((s => { let i = this.getdata("@chavy_boxjs_userCfgs.httpapi"); i = i ? i.replace(/\n/g, "").trim() : i; let o = this.getdata("@chavy_boxjs_userCfgs.httpapi_timeout"); o = o ? 1 * o : 20, o = e && e.timeout ? e.timeout : o; const [r, a] = i.split("@"), n = { url: `http://${a}/v1/scripting/evaluate`, body: { script_text: t, mock_type: "cron", timeout: o }, headers: { "X-Key": r, Accept: "*/*" }, timeout: o }; this.post(n, ((t, e, i) => s(i))) })).catch((t => this.logErr(t))) } loaddata() { if (!this.isNode()) return {}; { this.fs = this.fs ? this.fs : require("fs"), this.path = this.path ? this.path : require("path"); const t = this.path.resolve(this.dataFile), e = this.path.resolve(process.cwd(), this.dataFile), s = this.fs.existsSync(t), i = !s && this.fs.existsSync(e); if (!s && !i) return {}; { const i = s ? t : e; try { return JSON.parse(this.fs.readFileSync(i)) } catch (t) { return {} } } } } writedata() { if (this.isNode()) { this.fs = this.fs ? this.fs : require("fs"), this.path = this.path ? this.path : require("path"); const t = this.path.resolve(this.dataFile), e = this.path.resolve(process.cwd(), this.dataFile), s = this.fs.existsSync(t), i = !s && this.fs.existsSync(e), o = JSON.stringify(this.data); s ? this.fs.writeFileSync(t, o) : i ? this.fs.writeFileSync(e, o) : this.fs.writeFileSync(t, o) } } lodash_get(t, e, s) { const i = e.replace(/\[(\d+)\]/g, ".$1").split("."); let o = t; for (const t of i) if (o = Object(o)[t], void 0 === o) return s; return o } lodash_set(t, e, s) { return Object(t) !== t || (Array.isArray(e) || (e = e.toString().match(/[^.[\]]+/g) || []), e.slice(0, -1).reduce(((t, s, i) => Object(t[s]) === t[s] ? t[s] : t[s] = Math.abs(e[i + 1]) >> 0 == +e[i + 1] ? [] : {}), t)[e[e.length - 1]] = s), t } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), o = s ? this.getval(s) : ""; if (o) try { const t = JSON.parse(o); e = t ? this.lodash_get(t, i, "") : e } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, o] = /^@(.*?)\.(.*?)$/.exec(e), r = this.getval(i), a = i ? "null" === r ? null : r || "{}" : "{}"; try { const e = JSON.parse(a); this.lodash_set(e, o, t), s = this.setval(JSON.stringify(e), i) } catch (e) { const r = {}; this.lodash_set(r, o, t), s = this.setval(JSON.stringify(r), i) } } else s = this.setval(t, e); return s } getval(t) { switch (this.getEnv()) { case "Surge": case "Loon": case "Stash": case "Shadowrocket": return $persistentStore.read(t); case "Quantumult X": return $prefs.valueForKey(t); case "Node.js": return this.data = this.loaddata(), this.data[t]; default: return this.data && this.data[t] || null } } setval(t, e) { switch (this.getEnv()) { case "Surge": case "Loon": case "Stash": case "Shadowrocket": return $persistentStore.write(t, e); case "Quantumult X": return $prefs.setValueForKey(t, e); case "Node.js": return this.data = this.loaddata(), this.data[e] = t, this.writedata(), !0; default: return this.data && this.data[e] || null } } initGotEnv(t) { this.got = this.got ? this.got : require("got"), this.cktough = this.cktough ? this.cktough : require("tough-cookie"), this.ckjar = this.ckjar ? this.ckjar : new this.cktough.CookieJar, t && (t.headers = t.headers ? t.headers : {}, t && (t.headers = t.headers ? t.headers : {}, void 0 === t.headers.cookie && void 0 === t.headers.Cookie && void 0 === t.cookieJar && (t.cookieJar = this.ckjar))) } get(t, e = (() => { })) { switch (t.headers && (delete t.headers["Content-Type"], delete t.headers["Content-Length"], delete t.headers["content-type"], delete t.headers["content-length"]), t.params && (t.url += "?" + this.queryStr(t.params)), void 0 === t.followRedirect || t.followRedirect || ((this.isSurge() || this.isLoon()) && (t["auto-redirect"] = !1), this.isQuanX() && (t.opts ? t.opts.redirection = !1 : t.opts = { redirection: !1 })), this.getEnv()) { case "Surge": case "Loon": case "Stash": case "Shadowrocket": default: this.isSurge() && this.isNeedRewrite && (t.headers = t.headers || {}, Object.assign(t.headers, { "X-Surge-Skip-Scripting": !1 })), $httpClient.get(t, ((t, s, i) => { !t && s && (s.body = i, s.statusCode = s.status ? s.status : s.statusCode, s.status = s.statusCode), e(t, s, i) })); break; case "Quantumult X": this.isNeedRewrite && (t.opts = t.opts || {}, Object.assign(t.opts, { hints: !1 })), $task.fetch(t).then((t => { const { statusCode: s, statusCode: i, headers: o, body: r, bodyBytes: a } = t; e(null, { status: s, statusCode: i, headers: o, body: r, bodyBytes: a }, r, a) }), (t => e(t && t.error || "UndefinedError"))); break; case "Node.js": let s = require("iconv-lite"); this.initGotEnv(t), this.got(t).on("redirect", ((t, e) => { try { if (t.headers["set-cookie"]) { const s = t.headers["set-cookie"].map(this.cktough.Cookie.parse).toString(); s && this.ckjar.setCookieSync(s, null), e.cookieJar = this.ckjar } } catch (t) { this.logErr(t) } })).then((t => { const { statusCode: i, statusCode: o, headers: r, rawBody: a } = t, n = s.decode(a, this.encoding); e(null, { status: i, statusCode: o, headers: r, rawBody: a, body: n }, n) }), (t => { const { message: i, response: o } = t; e(i, o, o && s.decode(o.rawBody, this.encoding)) })); break } } post(t, e = (() => { })) { const s = t.method ? t.method.toLocaleLowerCase() : "post"; switch (t.body && t.headers && !t.headers["Content-Type"] && !t.headers["content-type"] && (t.headers["content-type"] = "application/x-www-form-urlencoded"), t.headers && (delete t.headers["Content-Length"], delete t.headers["content-length"]), void 0 === t.followRedirect || t.followRedirect || ((this.isSurge() || this.isLoon()) && (t["auto-redirect"] = !1), this.isQuanX() && (t.opts ? t.opts.redirection = !1 : t.opts = { redirection: !1 })), this.getEnv()) { case "Surge": case "Loon": case "Stash": case "Shadowrocket": default: this.isSurge() && this.isNeedRewrite && (t.headers = t.headers || {}, Object.assign(t.headers, { "X-Surge-Skip-Scripting": !1 })), $httpClient[s](t, ((t, s, i) => { !t && s && (s.body = i, s.statusCode = s.status ? s.status : s.statusCode, s.status = s.statusCode), e(t, s, i) })); break; case "Quantumult X": t.method = s, this.isNeedRewrite && (t.opts = t.opts || {}, Object.assign(t.opts, { hints: !1 })), $task.fetch(t).then((t => { const { statusCode: s, statusCode: i, headers: o, body: r, bodyBytes: a } = t; e(null, { status: s, statusCode: i, headers: o, body: r, bodyBytes: a }, r, a) }), (t => e(t && t.error || "UndefinedError"))); break; case "Node.js": let i = require("iconv-lite"); this.initGotEnv(t); const { url: o, ...r } = t; this.got[s](o, r).then((t => { const { statusCode: s, statusCode: o, headers: r, rawBody: a } = t, n = i.decode(a, this.encoding); e(null, { status: s, statusCode: o, headers: r, rawBody: a, body: n }, n) }), (t => { const { message: s, response: o } = t; e(s, o, o && i.decode(o.rawBody, this.encoding)) })); break } } time(t, e = null) { const s = e ? new Date(e) : new Date; let i = { "M+": s.getMonth() + 1, "d+": s.getDate(), "H+": s.getHours(), "m+": s.getMinutes(), "s+": s.getSeconds(), "q+": Math.floor((s.getMonth() + 3) / 3), S: s.getMilliseconds() }; /(y+)/.test(t) && (t = t.replace(RegExp.$1, (s.getFullYear() + "").substr(4 - RegExp.$1.length))); for (let e in i) new RegExp("(" + e + ")").test(t) && (t = t.replace(RegExp.$1, 1 == RegExp.$1.length ? i[e] : ("00" + i[e]).substr(("" + i[e]).length))); return t } queryStr(t) { let e = ""; for (const s in t) { let i = t[s]; null != i && "" !== i && ("object" == typeof i && (i = JSON.stringify(i)), e += `${s}=${i}&`) } return e = e.substring(0, e.length - 1), e } msg(e = t, s = "", i = "", o = {}) { const r = t => { const { $open: e, $copy: s, $media: i, $mediaMime: o } = t; switch (typeof t) { case void 0: return t; case "string": switch (this.getEnv()) { case "Surge": case "Stash": default: return { url: t }; case "Loon": case "Shadowrocket": return t; case "Quantumult X": return { "open-url": t }; case "Node.js": return }case "object": switch (this.getEnv()) { case "Surge": case "Stash": case "Shadowrocket": default: { const r = {}; let a = t.openUrl || t.url || t["open-url"] || e; a && Object.assign(r, { action: "open-url", url: a }); let n = t["update-pasteboard"] || t.updatePasteboard || s; if (n && Object.assign(r, { action: "clipboard", text: n }), i) { let t, e, s; if (i.startsWith("http")) t = i; else if (i.startsWith("data:")) { const [t] = i.split(";"), [, o] = i.split(","); e = o, s = t.replace("data:", "") } else { e = i, s = (t => { const e = { JVBERi0: "application/pdf", R0lGODdh: "image/gif", R0lGODlh: "image/gif", iVBORw0KGgo: "image/png", "/9j/": "image/jpg" }; for (var s in e) if (0 === t.indexOf(s)) return e[s]; return null })(i) } Object.assign(r, { "media-url": t, "media-base64": e, "media-base64-mime": o ?? s }) } return Object.assign(r, { "auto-dismiss": t["auto-dismiss"], sound: t.sound }), r } case "Loon": { const s = {}; let o = t.openUrl || t.url || t["open-url"] || e; o && Object.assign(s, { openUrl: o }); let r = t.mediaUrl || t["media-url"]; return i?.startsWith("http") && (r = i), r && Object.assign(s, { mediaUrl: r }), console.log(JSON.stringify(s)), s } case "Quantumult X": { const o = {}; let r = t["open-url"] || t.url || t.openUrl || e; r && Object.assign(o, { "open-url": r }); let a = t["media-url"] || t.mediaUrl; i?.startsWith("http") && (a = i), a && Object.assign(o, { "media-url": a }); let n = t["update-pasteboard"] || t.updatePasteboard || s; return n && Object.assign(o, { "update-pasteboard": n }), console.log(JSON.stringify(o)), o } case "Node.js": return }default: return } }; if (!this.isMute) switch (this.getEnv()) { case "Surge": case "Loon": case "Stash": case "Shadowrocket": default: $notification.post(e, s, i, r(o)); break; case "Quantumult X": $notify(e, s, i, r(o)); break; case "Node.js": break }if (!this.isMuteLog) { let t = ["", "==============📣系统通知📣=============="]; t.push(e), s && t.push(s), i && t.push(i), console.log(t.join("\n")), this.logs = this.logs.concat(t) } } debug(...t) { this.logLevels[this.logLevel] <= this.logLevels.debug && (t.length > 0 && (this.logs = [...this.logs, ...t]), console.log(`${this.logLevelPrefixs.debug}${t.map((t => t ?? String(t))).join(this.logSeparator)}`)) } info(...t) { this.logLevels[this.logLevel] <= this.logLevels.info && (t.length > 0 && (this.logs = [...this.logs, ...t]), console.log(`${this.logLevelPrefixs.info}${t.map((t => t ?? String(t))).join(this.logSeparator)}`)) } warn(...t) { this.logLevels[this.logLevel] <= this.logLevels.warn && (t.length > 0 && (this.logs = [...this.logs, ...t]), console.log(`${this.logLevelPrefixs.warn}${t.map((t => t ?? String(t))).join(this.logSeparator)}`)) } error(...t) { this.logLevels[this.logLevel] <= this.logLevels.error && (t.length > 0 && (this.logs = [...this.logs, ...t]), console.log(`${this.logLevelPrefixs.error}${t.map((t => t ?? String(t))).join(this.logSeparator)}`)) } log(...t) { t.length > 0 && (this.logs = [...this.logs, ...t]), console.log(t.map((t => t ?? String(t))).join(this.logSeparator)) } logErr(t, e) { switch (this.getEnv()) { case "Surge": case "Loon": case "Stash": case "Shadowrocket": case "Quantumult X": default: this.log("", `❗️${this.name}, 错误!`, e, t); break; case "Node.js": this.log("", `❗️${this.name}, 错误!`, e, void 0 !== t.message ? t.message : t, t.stack); break } } wait(t) { return new Promise((e => setTimeout(e, t))) } done(t = {}) { const e = ((new Date).getTime() - this.startTime) / 1e3; switch (this.log("", `🔔${this.name}, 结束! 🕛 ${e} 秒`), this.log(), this.getEnv()) { case "Surge": case "Loon": case "Stash": case "Shadowrocket": case "Quantumult X": default: $done(t); break; case "Node.js": process.exit(1) } } }(t, e) }