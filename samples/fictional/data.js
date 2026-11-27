/* 虚构网文样例 · schema v2.0 全字段演示
 * 《青云签到三十年》——完全虚构的作品，用于展示网文特有的数据结构：
 * 境界体系、战力时间线、逐章摘要、伏笔台账、认知隔离。
 * 不涉及任何真实作品的版权。
 */
window.ATLAS_DATA = {
  meta: {
    schema_version: "2.0",
    title: "青云签到三十年",
    author: "示例作者",
    genre: "仙侠",
    platform: "番茄",
    status: "连载中",
    source_file: "qingyun.txt",
    chars: 920000,
    chapters: 300,
    analyzed_at: "2026-11-27T06:00:00Z",
    model: "manual",
    cost_cny: 0,
    elapsed_sec: 0,
    coverage: { chapters_done: 120, chapters_skipped: 180 },
    note: "虚构样例，用于演示 schema v2.0；章节数据仅摘录关键节点"
  },

  volumes: [
    { id: "v1", name: "杂役三年", ch_start: 1, ch_end: 40, summary: "林云穿越成青云宗杂役，靠签到系统偷偷修炼，从练气三层爬到九层。" },
    { id: "v2", name: "内门风云", ch_start: 41, ch_end: 120, summary: "入内门，与赵虎一系正面冲突，筑基成功，牵出血刀门密探。" }
  ],

  realms: [
    { id: "r_qi", name: "练气", order: 1, stages: ["一层","二层","三层","四层","五层","六层","七层","八层","九层"], first_ch: 1, desc: "引气入体，共九层。宗门杂役大多停在一两层。" },
    { id: "r_zhuji", name: "筑基", order: 2, stages: ["初期","中期","后期"], first_ch: 45, desc: "筑就道基，可御器飞行，内门弟子的门槛。" },
    { id: "r_jindan", name: "金丹", order: 3, stages: ["初期","中期","后期"], first_ch: 98, desc: "结成金丹，寿元三百，可为一峰之主。" },
    { id: "r_yuanying", name: "元婴", order: 4, stages: ["初期","中期","后期"], first_ch: 260, desc: "元婴出窍，宗门宗主级战力。" }
  ],

  entities: [
    { id: "e_linyun", name: "林云", type: "character", group: "青云宗", parent: "e_qingyunzong",
      aliases: ["云哥", "林师弟", "林师兄"],
      desc: "主角。穿越前是程序员，附身青云宗杂役。性格谨慎多疑，靠签到系统悄悄修炼，从不显山露水。",
      first_ch: 1, last_ch: null,
      attrs: { 性格: "谨慎、护短", 金手指: "签到系统", 目标: "查明父亲死因" },
      ranks: ["杂役", "外门弟子", "内门弟子"],
      power_history: [
        { ch: 1,  realm: "r_qi", stage: "三层", note: "原身遗留" },
        { ch: 8,  realm: "r_qi", stage: "五层", note: "签到得聚气丹" },
        { ch: 18, realm: "r_qi", stage: "七层", note: "后山禁地奇遇" },
        { ch: 45, realm: "r_zhuji", stage: "初期", note: "服筑基丹" },
        { ch: 78, realm: "r_zhuji", stage: "后期", note: "剑冢悟道" },
        { ch: 98, realm: "r_jindan", stage: "初期", note: "血战突破" }
      ] },

    { id: "e_suqing", name: "苏清", type: "character", group: "青云宗", parent: "e_qingyunzong",
      aliases: ["苏师姐", "清剑仙子"],
      desc: "青云宗真传弟子，剑修。外表冷傲，实则心软。第 87 章认出林云的玉佩是掌门信物，是全书转折点。",
      first_ch: 15, last_ch: null,
      attrs: { 性格: "冷傲、重诺", 剑名: "霜华" },
      power_history: [
        { ch: 15, realm: "r_zhuji", stage: "后期", note: "登场即筑基后期" },
        { ch: 98, realm: "r_jindan", stage: "中期", note: "剑冢同悟" }
      ] },

    { id: "e_zhaohu", name: "赵虎", type: "character", group: "青云宗", parent: "e_qingyunzong",
      aliases: ["赵师兄"],
      desc: "外门弟子，仗着叔叔王执事的势，长期欺压杂役。第 60 章被林云当众击败后怀恨投靠血刀门。",
      first_ch: 4, last_ch: null,
      attrs: { 性格: "跋扈、睚眦必报" },
      power_history: [
        { ch: 4,  realm: "r_qi", stage: "六层", note: "登场" },
        { ch: 60, realm: "r_qi", stage: "九层", note: "被击败时" }
      ] },

    { id: "e_wangzhishi", name: "王执事", type: "character", group: "青云宗", parent: "e_qingyunzong",
      aliases: ["王长老"],
      desc: "外门执事，赵虎的叔父。掌管杂役分派，克扣月例。第 75 章因通敌被废去修为逐出宗门。",
      first_ch: 6, last_ch: 75,
      attrs: { 性格: "贪吝、欺软怕硬" },
      power_history: [{ ch: 6, realm: "r_zhuji", stage: "中期", note: "登场" }] },

    { id: "e_qingyunzi", name: "青云子", type: "character", group: "青云宗", parent: "e_qingyunzong",
      aliases: ["宗主"],
      desc: "青云宗宗主，元婴初期。常年闭关，宗门事务由三位长老打理。与林云的父亲有旧。",
      first_ch: 25, last_ch: null,
      attrs: { 性格: "深沉、护短" },
      power_history: [{ ch: 25, realm: "r_yuanying", stage: "初期", note: "闭关中" }] },

    { id: "e_lizhanglao", name: "李长老", type: "character", group: "青云宗", parent: "e_qingyunzong",
      aliases: ["传功长老"],
      desc: "传功长老，金丹中期。第 45 章主持筑基试，看中林云心性，收为内门弟子。",
      first_ch: 30, last_ch: null,
      attrs: { 性格: "方正、惜才" },
      power_history: [{ ch: 30, realm: "r_jindan", stage: "中期", note: "登场" }] },

    { id: "e_laoqigai", name: "老乞丐", type: "character", group: "其他", parent: null,
      aliases: ["疯乞丐", "上任宗主"],
      desc: "第 5 章在集市被林云施舍的乞丐。真实身份是青云宗上任宗主，因走火入魔隐姓埋名。第 87 章揭示。",
      first_ch: 5, last_ch: null,
      attrs: { 真实身份: "上任宗主玄阳", 状态: "走火入魔，记忆残缺" },
      power_history: [{ ch: 5, realm: "r_yuanying", stage: "后期", note: "表面疯癫，实力仍在" }] },

    { id: "e_xuewuhen", name: "血无痕", type: "character", group: "血刀门", parent: "e_xuedaomen",
      aliases: ["血少主"],
      desc: "血刀门少主，筑基后期。安插密探入青云宗，图谋后山禁地。第 100 章与林云血战。",
      first_ch: 55, last_ch: null,
      attrs: { 性格: "阴狠、自负" },
      power_history: [
        { ch: 55,  realm: "r_zhuji", stage: "后期", note: "登场" },
        { ch: 100, realm: "r_jindan", stage: "初期", note: "血战突破" }
      ] },

    { id: "e_chenshi", name: "陈实", type: "character", group: "青云宗", parent: "e_qingyunzong",
      aliases: ["陈师兄"],
      desc: "杂役出身的外门弟子，林云在宗内唯一的朋友。第 22 章被赵虎设计打断腿，此后帮林云打理外务。",
      first_ch: 7, last_ch: null,
      attrs: { 性格: "憨厚、讲义气" },
      power_history: [{ ch: 7, realm: "r_qi", stage: "四层", note: "登场" }] },

    { id: "e_xiaocui", name: "小翠", type: "character", group: "青云宗", parent: "e_qingyunzong",
      aliases: [],
      desc: "杂役院的丫头，负责洒扫。第 12 章给林云送饭时提起阿福临死前的话，成为关键线索。",
      first_ch: 9, last_ch: null,
      attrs: { 性格: "胆怯、心细" },
      power_history: [{ ch: 9, realm: "r_qi", stage: "一层", note: "凡人水准" }] },

    { id: "e_afu", name: "阿福", type: "character", group: "青云宗", parent: "e_qingyunzong",
      aliases: [],
      desc: "杂役，林云原身的好友。第 12 章因「失足坠崖」身亡，实为发现王执事克扣证据被灭口。",
      first_ch: 2, last_ch: 12,
      attrs: { 死因: "被灭口，伪造成失足" },
      power_history: [{ ch: 2, realm: "r_qi", stage: "二层", note: "登场" }] },

    { id: "e_zhouzhishi", name: "周执事", type: "character", group: "血刀门", parent: "e_xuedaomen",
      aliases: ["周管事"],
      desc: "血刀门安插在青云宗的密探，伪装成采买执事二十年。第 75 章暴露。",
      first_ch: 20, last_ch: 76,
      attrs: { 真实身份: "血刀门密探" },
      power_history: [{ ch: 20, realm: "r_zhuji", stage: "初期", note: "伪装时压低修为" }] },

    { id: "e_xuanyangzi", name: "玄阳子", type: "character", group: "天机阁", parent: "e_tianjige",
      aliases: ["天机老人"],
      desc: "天机阁阁主，擅长推演。第 30 章给出「青云将倾，玉碎人全」八字预言，贯穿全书。",
      first_ch: 30, last_ch: null,
      attrs: { 性格: "疏离、言不尽意" },
      power_history: [{ ch: 30, realm: "r_yuanying", stage: "后期", note: "深不可测" }] },

    { id: "e_qingyunzong", name: "青云宗", type: "org", group: "青云宗", parent: null,
      aliases: ["青云"],
      desc: "东域三大宗门之一，宗主青云子。内部分杂役、外门、内门、真传四级。",
      first_ch: 1, last_ch: null,
      attrs: { 等级: "东域三大宗门" },
      ranks: ["杂役", "外门弟子", "内门弟子", "真传弟子", "长老", "宗主"] },

    { id: "e_xuedaomen", name: "血刀门", type: "org", group: "血刀门", parent: null,
      aliases: ["血刀"],
      desc: "邪道宗门，以血炼功法闻名。少主血无痕图谋青云宗后山禁地。",
      first_ch: 20, last_ch: null,
      attrs: { 性质: "邪道宗门" },
      ranks: ["弟子", "血卫", "堂主", "少主", "门主"] },

    { id: "e_tianjige", name: "天机阁", type: "org", group: "天机阁", parent: null,
      aliases: ["天机"],
      desc: "超然物外的推演组织，不参与争斗，只卖消息和预言。",
      first_ch: 30, last_ch: null,
      attrs: { 性质: "中立情报组织" },
      ranks: ["阁员", "执事", "阁主"] },

    { id: "e_yupei", name: "云纹玉佩", type: "item", group: "青云宗", parent: null,
      aliases: ["玉佩"],
      desc: "林云父亲留下的遗物，刻有云纹。第 87 章被苏清认出是青云宗掌门信物。",
      first_ch: 3, last_ch: null,
      attrs: { 品阶: "掌门信物" } },

    { id: "e_xuantiejian", name: "玄铁剑", type: "item", group: "青云宗", parent: null,
      aliases: ["黑剑"],
      desc: "第 18 章在后山禁地获得，无锋无锷，重三十六斤。签到系统判定为「凡品巅峰」。",
      first_ch: 18, last_ch: null,
      attrs: { 品阶: "凡品巅峰", 重量: "三十六斤" } }
  ],

  relations: [
    { s: "e_linyun", t: "e_suqing", type: "romance", label: "相知", weight: 0.7, first_ch: 15, evidence: ["ch15:p20"] },
    { s: "e_linyun", t: "e_suqing", type: "alliance", label: "并肩", weight: 0.8, first_ch: 98, evidence: ["ch98:p12"] },
    { s: "e_linyun", t: "e_laoqigai", type: "alliance", label: "一饭之恩", weight: 0.9, first_ch: 5, evidence: ["ch05:p18"] },
    { s: "e_linyun", t: "e_lizhanglao", type: "mentorship", label: "师徒", weight: 0.85, first_ch: 45, evidence: ["ch45:p06"] },
    { s: "e_linyun", t: "e_chenshi", type: "social", label: "挚友", weight: 0.9, first_ch: 7, evidence: ["ch07:p14"] },
    { s: "e_linyun", t: "e_xiaocui", type: "social", label: "同院", weight: 0.4, first_ch: 9, evidence: ["ch09:p08"] },
    { s: "e_linyun", t: "e_afu", type: "social", label: "旧友", weight: 0.7, first_ch: 2, evidence: ["ch02:p10"] },
    { s: "e_linyun", t: "e_zhaohu", type: "conflict", label: "宿怨", weight: 0.85, first_ch: 4, evidence: ["ch04:p12", "ch60:p18"] },
    { s: "e_linyun", t: "e_wangzhishi", type: "conflict", label: "被克扣", weight: 0.7, first_ch: 6, evidence: ["ch06:p16"] },
    { s: "e_linyun", t: "e_xuewuhen", type: "conflict", label: "生死仇敌", weight: 0.95, first_ch: 55, evidence: ["ch100:p08"] },
    { s: "e_zhaohu", t: "e_wangzhishi", type: "kinship", label: "叔侄", weight: 0.8, first_ch: 6, evidence: ["ch06:p14"] },
    { s: "e_zhouzhishi", t: "e_xuewuhen", type: "service", label: "上下线", weight: 0.8, first_ch: 22, evidence: ["ch22:p20"] },
    { s: "e_zhouzhishi", t: "e_xuedaomen", type: "service", label: "密探", weight: 0.9, first_ch: 20, evidence: ["ch75:p10"] },
    { s: "e_zhouzhishi", t: "e_qingyunzong", type: "service", label: "伪装执事", weight: 0.4, first_ch: 20, evidence: ["ch20:p06"] },
    { s: "e_zhaohu", t: "e_xuedaomen", type: "alliance", label: "投靠", weight: 0.7, first_ch: 62, evidence: ["ch62:p14"] },
    { s: "e_qingyunzi", t: "e_qingyunzong", type: "service", label: "宗主", weight: 0.95, first_ch: 25, evidence: ["ch25:p04"] },
    { s: "e_lizhanglao", t: "e_qingyunzong", type: "service", label: "传功长老", weight: 0.85, first_ch: 30, evidence: ["ch30:p02"] },
    { s: "e_suqing", t: "e_qingyunzong", type: "service", label: "真传弟子", weight: 0.85, first_ch: 15, evidence: ["ch15:p06"] },
    { s: "e_qingyunzi", t: "e_laoqigai", type: "social", label: "同代旧识", weight: 0.6, first_ch: 87, evidence: ["ch87:p16"] },
    { s: "e_xuanyangzi", t: "e_tianjige", type: "service", label: "阁主", weight: 0.9, first_ch: 30, evidence: ["ch30:p20"] },
    { s: "e_xuanyangzi", t: "e_qingyunzi", type: "social", label: "旧交", weight: 0.5, first_ch: 30, evidence: ["ch30:p22"] },
    { s: "e_qingyunzong", t: "e_xuedaomen", type: "conflict", label: "正邪对峙", weight: 0.8, first_ch: 20, evidence: ["ch75:p12"] },
    { s: "e_qingyunzong", t: "e_tianjige", type: "social", label: "买卖消息", weight: 0.4, first_ch: 30, evidence: ["ch30:p18"] },
    { s: "e_linyun", t: "e_qingyunzong", type: "service", label: "杂役→内门", weight: 0.6, first_ch: 1, evidence: ["ch01:p04", "ch45:p08"] },
    { s: "e_linyun", t: "e_yupei", type: "social", label: "持有", weight: 0.8, first_ch: 3, evidence: ["ch03:p14"] }
  ],

  chapters: [
    { ch: 1, title: "穿越成杂役", words: 3120, volume: "v1", summary: "林云穿越到青云宗杂役身上，原身刚被打死。脑中响起签到系统的声音。", hook: "系统提示：七日未签到，宿主神魂俱灭", hook_type: "危机", emotion: "压抑", tension: 0.55, new_entities: ["e_linyun"], new_foreshadows: ["f_xitong"] },
    { ch: 2, title: "阿福", words: 2980, volume: "v1", summary: "同屋的阿福照顾他，告诉他杂役院规矩。林云第一次签到，得到一粒劣质聚气丹。", hook: "阿福欲言又止：有些事你别打听", hook_type: "悬念", emotion: "平", tension: 0.35, new_entities: ["e_afu"], new_foreshadows: [] },
    { ch: 3, title: "父亲的遗物", words: 3240, volume: "v1", summary: "林云整理原身遗物，发现一枚刻着云纹的玉佩，系统提示「无法鉴定」。", hook: "系统罕见地沉默了", hook_type: "悬念", emotion: "压抑", tension: 0.45, new_entities: ["e_yupei"], new_foreshadows: ["f_yupei"] },
    { ch: 4, title: "赵虎", words: 3010, volume: "v1", summary: "外门弟子赵虎来杂役院索要月例，林云交不出，被打了一顿。", hook: "赵虎冷笑：下个月翻倍", hook_type: "冲突", emotion: "压抑", tension: 0.6, new_entities: ["e_zhaohu"], new_foreshadows: [] },
    { ch: 5, title: "一枚铜钱", words: 2870, volume: "v1", summary: "林云下山采买，把仅剩的铜钱给了一个疯乞丐。乞丐盯着他看了很久。", hook: "乞丐喃喃：云纹……你姓林？", hook_type: "悬念", emotion: "温情", tension: 0.4, new_entities: ["e_laoqigai"], new_foreshadows: ["f_qigai"] },
    { ch: 6, title: "克扣", words: 3260, volume: "v1", summary: "王执事以「杂役损耗」为名克扣全院月例，林云发现账目有问题。", hook: "账本上的数字，少了整整三成", hook_type: "悬念", emotion: "压抑", tension: 0.5, new_entities: ["e_wangzhishi"], new_foreshadows: ["f_zhangben"] },
    { ch: 7, title: "陈实", words: 2950, volume: "v1", summary: "杂役出身的外门弟子陈实帮林云解围，两人结识。", hook: "陈实压低声音：王执事上面有人", hook_type: "悬念", emotion: "平", tension: 0.35, new_entities: ["e_chenshi"], new_foreshadows: [] },
    { ch: 8, title: "连签七日", words: 3080, volume: "v1", summary: "林云连续签到七日，得聚气丹三粒，一夜突破至练气五层。", hook: "他听见院外有脚步声停了一下", hook_type: "危机", emotion: "爽", tension: 0.6, new_entities: [], new_foreshadows: ["f_benjian"] },
    { ch: 9, title: "小翠", words: 2760, volume: "v1", summary: "杂役院的丫头小翠给林云送饭，提到阿福最近总往账房跑。", hook: "小翠：阿福哥说他要发财了", hook_type: "悬念", emotion: "平", tension: 0.4, new_entities: ["e_xiaocui"], new_foreshadows: [] },
    { ch: 10, title: "山雨", words: 3140, volume: "v1", summary: "林云察觉阿福神色慌张，劝他别掺和账房的事，阿福不听。", hook: "阿福：等这票干完，我请你喝酒", hook_type: "悬念", emotion: "压抑", tension: 0.5, new_entities: [], new_foreshadows: [] },
    { ch: 11, title: "坠崖", words: 3290, volume: "v1", summary: "阿福被发现死在断崖下，宗门定性为「失足」。林云在他枕下摸到半张残页。", hook: "残页只剩三个字：血、刀、门", hook_type: "反转", emotion: "悲", tension: 0.85, new_entities: [], new_foreshadows: ["f_canye"] },
    { ch: 12, title: "他没说出口的话", words: 3050, volume: "v1", summary: "小翠告诉林云，阿福死前一晚说过「要是出事，把这东西给林云」。但东西不见了。", hook: "东西去哪了？", hook_type: "悬念", emotion: "悲", tension: 0.7, new_entities: [], new_foreshadows: ["f_dongxi"] },
    { ch: 15, title: "霜华", words: 3320, volume: "v1", summary: "真传弟子苏清下山历练路过杂役院，林云第一次见到筑基后期剑修的威势。", hook: "苏清回头看了他一眼", hook_type: "悬念", emotion: "平", tension: 0.45, new_entities: ["e_suqing"], new_foreshadows: ["f_jiansui"] },
    { ch: 18, title: "后山禁地", words: 3410, volume: "v1", summary: "林云误入后山禁地，在石台上签到，得到玄铁剑，修为突破至练气七层。", hook: "石台下的刻字：青云子留", hook_type: "悬念", emotion: "爽", tension: 0.75, new_entities: ["e_xuantiejian"], new_foreshadows: ["f_jindi"] },
    { ch: 20, title: "采买执事", words: 2980, volume: "v1", summary: "周执事来杂役院查账，林云发现他和王执事交换了一个眼神。", hook: "两人的袖口，都沾着红线", hook_type: "悬念", emotion: "紧张", tension: 0.6, new_entities: ["e_zhouzhishi", "e_xuedaomen"], new_foreshadows: ["f_hongxian"] },
    { ch: 45, title: "筑基", words: 3560, volume: "v2", summary: "李长老主持筑基试，林云服下签到所得的筑基丹，一举成功，被收为内门弟子。", hook: "李长老：你这根基，不像杂役出身", hook_type: "悬念", emotion: "爽", tension: 0.85, new_entities: ["e_lizhanglao"], new_foreshadows: ["f_chushen"] },
    { ch: 60, title: "当众一战", words: 3480, volume: "v2", summary: "赵虎挑衅，林云在演武场当众击败练气九层的他，全宗哗然。", hook: "赵虎跪地咬牙：你会后悔的", hook_type: "冲突", emotion: "爽", tension: 0.9, new_entities: [], new_foreshadows: [] ,
      battles: [{ a: "e_linyun", b: "e_zhaohu", result: "win", gap: -2, note: "练气七层越两级击败九层，靠玄铁剑" }] },
    { ch: 87, title: "云纹", words: 3610, volume: "v2", summary: "苏清看到林云的玉佩，认出是掌门信物，告知他父亲当年是青云宗的人。老乞丐的身份同时揭晓。", hook: "苏清：这玉佩，本该在宗主手里", hook_type: "反转", emotion: "紧张", tension: 0.95, new_entities: [], new_foreshadows: [] },
    { ch: 98, title: "血战突破", words: 3720, volume: "v2", summary: "血无痕夜袭，林云在生死间结成金丹，与苏清联手击退。", hook: "血无痕逃走时留下一句：你父亲欠我们的", hook_type: "危机", emotion: "爽", tension: 1.0, new_entities: [], new_foreshadows: ["f_fuzhai"],
      battles: [{ a: "e_linyun", b: "e_xuewuhen", result: "draw", gap: -1, note: "金丹初期对筑基后期，靠苏清助战" }] },
    { ch: 120, title: "第一卷末", words: 3040, volume: "v2", summary: "林云入内门满一年，修为金丹初期。宗门开始调查密探，风暴将至。", hook: "宗主出关，第一句话：查林云", hook_type: "悬念", emotion: "紧张", tension: 0.8, new_entities: [], new_foreshadows: [] }
  ],

  foreshadows: [
    { id: "f_yupei", content: "父亲留下的云纹玉佩，系统无法鉴定", plant_ch: 3, plant_quote: "ch03:p14",
      payoff_ch: 87, payoff_quote: "ch87:p06", status: "paid", thread: "身世之谜", importance: 1.0,
      note: "第 87 章揭示为掌门信物，是全书最大转折" },
    { id: "f_qigai", content: "疯乞丐认出云纹，问「你姓林？」", plant_ch: 5, plant_quote: "ch05:p18",
      payoff_ch: 87, payoff_quote: "ch87:p16", status: "paid", thread: "身世之谜", importance: 0.95,
      note: "乞丐即上任宗主玄阳" },
    { id: "f_xitong", content: "签到系统的来源与代价", plant_ch: 1, plant_quote: "ch01:p06",
      payoff_ch: null, status: "overdue", thread: "金手指", importance: 0.9,
      note: "至今未解释，已超过阈值 50 章，读者开始追问" },
    { id: "f_zhangben", content: "王执事克扣月例的账本", plant_ch: 6, plant_quote: "ch06:p16",
      payoff_ch: 75, payoff_quote: "ch75:p08", status: "paid", thread: "宗门内斗", importance: 0.7,
      note: "第 75 章成为扳倒王执事的证据" },
    { id: "f_canye", content: "阿福枕下的半张残页，只剩「血刀门」三字", plant_ch: 11, plant_quote: "ch11:p22",
      payoff_ch: null, status: "overdue", thread: "血刀门", importance: 0.85, note: "指向周执事" },
    { id: "f_dongxi", content: "阿福托小翠转交的东西不见了", plant_ch: 12, plant_quote: "ch12:p16",
      payoff_ch: null, status: "overdue", thread: "血刀门", importance: 0.8, note: "被周执事截走" },
    { id: "f_jiansui", content: "苏清剑穗上的一缕黑线", plant_ch: 15, plant_quote: "ch15:p18",
      payoff_ch: null, status: "overdue", thread: "苏清身世", importance: 0.6, note: "与血刀门血炼术有关" },
    { id: "f_jindi", content: "后山禁地石台下「青云子留」四字", plant_ch: 18, plant_quote: "ch18:p20",
      payoff_ch: null, status: "overdue", thread: "禁地之谜", importance: 0.75, note: "宗主与禁地的关系" },
    { id: "f_hongxian", content: "周执事与王执事袖口同沾红线", plant_ch: 20, plant_quote: "ch20:p18",
      payoff_ch: 75, payoff_quote: "ch75:p12", status: "paid", thread: "血刀门", importance: 0.8, note: "通敌信物" },
    { id: "f_chushen", content: "李长老评「根基不像杂役出身」", plant_ch: 45, plant_quote: "ch45:p14",
      payoff_ch: null, status: "overdue", thread: "身世之谜", importance: 0.7, note: "指向父亲来历" },
    { id: "f_fuzhai", content: "血无痕：你父亲欠我们的", plant_ch: 98, plant_quote: "ch98:p18",
      payoff_ch: null, status: "planted", thread: "父辈恩怨", importance: 0.9, note: "下一卷主线" },
    { id: "f_benjian", content: "第 8 章突破当夜，院外停顿的脚步声", plant_ch: 8, plant_quote: "ch08:p22",
      payoff_ch: null, status: "overdue", thread: "暗线", importance: 0.5,
      note: "周执事在观察，但一直没交代，已成悬案" }
  ],

  knowledge: [
    { id: "k_zhuansheng", fact: "林云是穿越者，前世是现代程序员", truth_ch: 1, reader_known_ch: 1,
      known_by: [{ entity: "e_linyun", ch: 1 }] },
    { id: "k_yupei", fact: "云纹玉佩是青云宗掌门信物", truth_ch: 87, reader_known_ch: 87,
      known_by: [{ entity: "e_suqing", ch: 87 }, { entity: "e_linyun", ch: 87 }] },
    { id: "k_qigai", fact: "老乞丐是上任宗主玄阳，走火入魔", truth_ch: 87, reader_known_ch: 87,
      known_by: [{ entity: "e_qingyunzi", ch: 87 }, { entity: "e_laoqigai", ch: 87 }] },
    { id: "k_mifa", fact: "周执事是血刀门密探", truth_ch: 20, reader_known_ch: 20,
      known_by: [{ entity: "e_zhouzhishi", ch: 20 }, { entity: "e_xuewuhen", ch: 20 }, { entity: "e_qingyunzi", ch: 75 }] }
  ],

  places: [
    { id: "p_dongyu", name: "东域", parent: null, desc: "青云宗所在的大域，三大宗门并立。", first_ch: 1, attrs: {} },
    { id: "p_qingyunshan", name: "青云山", parent: "p_dongyu", desc: "青云宗山门所在，主峰九座。", first_ch: 1, attrs: {} },
    { id: "p_zayiyuan", name: "杂役院", parent: "p_qingyunshan", desc: "山脚最破的院子，住着百余杂役。", first_ch: 1, attrs: { 主人: "杂役" } },
    { id: "p_yanwuchang", name: "演武场", parent: "p_qingyunshan", desc: "外门弟子比试之地，第 60 章一战在此。", first_ch: 4, attrs: {} },
    { id: "p_houshan", name: "后山禁地", parent: "p_qingyunshan", desc: "历代宗主闭关之所，有石台与刻字。", first_ch: 18, attrs: { 禁令: "非宗主不得入" } },
    { id: "p_jishiji", name: "集市", parent: "p_dongyu", desc: "山门外的凡人集市，第 5 章施舍乞丐处。", first_ch: 5, attrs: {} }
  ],

  concepts: [
    { id: "c_qianDao", kind: "golden_finger", name: "签到系统", desc: "穿越自带的金手指。每日在特定地点签到可得奖励，地点越特殊，奖励越好。",
      first_ch: 1, rules: ["每日可签到一次", "地点越特殊，奖励品质越高", "连续签到有额外加成"], limits: ["每日仅一次，不可累积", "签到所得不可转让", "系统对自身来历始终沉默"] },
    { id: "c_pinjie", kind: "item_grade", name: "器物品阶", desc: "凡品、灵品、宝器、道器、仙器，各分下中上三档。", first_ch: 18, rules: [], limits: [] },
    { id: "c_xuelian", kind: "technique", name: "血炼术", desc: "血刀门核心功法，以生灵精血淬体，进境极快但易走火入魔。", first_ch: 20, rules: [], limits: [] },
    { id: "c_yuyan", kind: "prophecy", name: "青云将倾，玉碎人全", desc: "天机阁给出的八字预言，贯穿全书。", first_ch: 30, rules: [], limits: [] },
    { id: "c_gongxian", kind: "organization_rule", name: "贡献点制度", desc: "青云宗弟子以贡献点兑换功法、丹药、洞府。", first_ch: 45, rules: [], limits: [] }
  ]
};
