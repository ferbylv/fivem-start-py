import requests
import json

def getAiResult(input_content):
    # 1. 配置 API 端点和鉴权信息
    url = "https://api.coze.cn/v1/workflow/stream_run"
    token = "pat_OZ1T9g5SSOAaf3lMi730t9SSatPzLmfpA4tr03aMvjtzbzu8ZOTiZVDs5LADoff9"
    workflow_id = "7550915870744395810"

    # 2. 准备 Headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 3. 准备输入数据 (Payload)
    # 为了代码整洁，我们将长文本单独定义
    # input_content = (
    #     "Q：角色名字\n"
    #     "A：安迪·凯文\n"
    #     "Q：角色背景\n"
    #     "A：安迪·凯文，23岁美国本土人。他生于洛圣都一个普通工薪社区，拥有一个满是暖意的家庭——父亲是工厂技工，手艺精湛且为人敦厚，母亲是社区超市收银员，温柔耐心，小他5岁的妹妹活泼懂事，是家中的开心果。父母勤恳劳作，虽不富裕，却总能把小家庭打理得温馨和睦，从小就教导安迪踏实做事、真诚待人。12岁时父亲因工厂事故离世，家庭支柱轰然倒塌，懂事的安迪早早扛起责任，课余时间打零工补贴家用，高中毕业后便跟随父亲生前的老友学机械维修，靠着踏实的手艺勉强支撑家用、陪伴母亲和妹妹。\n"
    #     "21岁母亲重病离世，安迪带着妹妹相依为命，可洛圣都生活成本高昂，他的兼职收入难以支撑两人开支，还得兼顾妹妹的学业。为了给妹妹更好的成长环境，也想换个安稳的地方重新开始，安迪将妹妹托付给东部的亲戚寄养，自己则四处寻找机会。他在旧金山唐人街的修车行打了半年工，偶然从同行口中得知圣安地列斯乡村地区，不仅生活成本低、环境安稳，当地农场主和居民对机械维修需求也大，便决心前往此地，希望能在那里站稳脚跟，攒够积蓄接回妹妹，重拾曾经的家庭温暖。\n\n"
    #     "安迪性格沉稳内敛，待人真诚温和，做事踏实认真、有韧劲，继承了父亲的动手天赋，车辆维修和简单改装手艺娴熟。短期他要在圣安地列斯找到稳定的维修工作，攒下第一笔积蓄；中期计划租下一个小铺面，开一家简易的便民修车行，稳定收入后接回妹妹；长期则希望把修车行经营得有声有色，给妹妹安稳的生活，在当地扎根立足，过平凡而踏实的日子。\n"
    #     "Q: 下列哪一项最符合 RP（角色扮演）的定义？\n"
    #     "A: 扮演一个有血有肉的人，行为会产生现实后果。\n"
    #     "Q: 如果你的角色在扮演中失败、受伤、甚至死亡，你会如何对待？\n"
    #     "A: 接受结果，并根据受伤或死亡情况进行合理扮演。\n"
    #     "Q: 当你在扮演中遇到违规或冲突时，正确的处理方式是什么？\n"
    #     "A: 继续完成当前 RP 场景，事后通过正确渠道举报。"
    # )
    # print(input_content)
    # return
    payload = {
        "workflow_id": workflow_id,
        "parameters": {
            "input": input_content
        }
    }

    # 4. 发送请求
    try:
        response = requests.post(url, headers=headers, json=payload, stream=True)
        response.raise_for_status()

        print("--- 提取的最终结果 ---")

        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')

                # 1. 识别 data: 开头的数据行
                if decoded_line.startswith("data:"):
                    json_str = decoded_line[5:]  # 去掉 'data:' 前缀

                    try:
                        data = json.loads(json_str)

                        # 2. 核心过滤逻辑：
                        # 只有当 node_type 是 'End' (结束节点) 且包含 'content' 字段时才输出
                        if data.get("node_type") == "End" and "content" in data:
                            # 3. 只打印 content 的内容
                            print(data["content"])

                            return data["content"]

                    except json.JSONDecodeError:
                        pass

    except requests.exceptions.RequestException as e:
        print(f"请求发生错误: {e}")