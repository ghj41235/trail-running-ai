"""
AI Service - Proxy to Kimi API with local fallback
All AI calls go through backend, frontend never touches API keys.
"""
import json
import requests


class AIService:
    """AI service that proxies requests to Kimi API with local fallback."""
    
    def __init__(self, api_key: str, endpoint: str = 'https://api.moonshot.cn/v1/chat/completions',
                 model: str = 'moonshot-v1-8k'):
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
    
    def generate_plan(self, params: dict) -> dict:
        """Generate training plan via Kimi API.
        
        Args:
            params: {'level', 'target_distance', 'weeks', 'weekly_distance'}
            
        Returns:
            Training plan dict
            
        Raises:
            Exception: If API call fails
        """
        if not self.api_key:
            raise Exception('API Key未配置')
        
        prompt = self._build_plan_prompt(params)
        
        resp = requests.post(
            self.endpoint,
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': self.model,
                'messages': [
                    {'role': 'system', 'content': '你是专业越野跑教练。必须返回严格JSON格式，不要Markdown代码块包裹，不要解释性文字。所有内容必须用中文。'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.7,
                'max_tokens': 4000
            },
            timeout=45
        )
        
        if resp.status_code != 200:
            raise Exception(f'Kimi API错误: {resp.status_code} {resp.text[:200]}')
        
        content = resp.json()['choices'][0]['message']['content']
        content = self._clean_json(content)
        
        return json.loads(content)
    
    def chat(self, message: str, context: dict = None) -> str:
        """AI coach chat.
        
        Args:
            message: User message
            context: Optional context dict
            
        Returns:
            AI response string
        """
        if not self.api_key:
            raise Exception('API Key未配置')
        
        system_msg = ('你是越野跑AI教练，回答简洁专业，控制在200字内。'
                      '你擅长越野跑训练、装备选择、比赛策略。'
                      '回答要实用具体，避免空话。所有内容必须用中文。')
        
        messages = [{'role': 'system', 'content': system_msg}]
        
        if context and context.get('history'):
            for h in context['history'][-4:]:  # Keep last 4 exchanges
                messages.append(h)
        
        messages.append({'role': 'user', 'content': message})
        
        resp = requests.post(
            self.endpoint,
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': self.model,
                'messages': messages,
                'temperature': 0.8,
                'max_tokens': 1000
            },
            timeout=30
        )
        
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']
    
    def generate_equipment_advice(self, route_data: dict) -> dict:
        """Generate equipment recommendations based on route."""
        if not self.api_key:
            raise Exception('API Key未配置')
        
        metrics = route_data.get('metrics', {})
        prompt = f"""基于以下越野跑路线信息，推荐装备（严格JSON格式）：
路线：{metrics.get('total_distance_km', 0)}km，爬升{metrics.get('total_ascent_m', 0)}m
平均坡度：{metrics.get('avg_gradient', 0)}%

要求：
1. 所有字段内容必须用中文
2. shoes.name 推荐具体热门品牌和型号（如Salomon Speedcross 6、HOKA Speedgoat 5、凯乐石Fuga DU等）
3. features 用中文描述特点
4. gear 根据路线时长判断是否推荐头灯（白天短距离不需要）
5. nutrition 要具体化

请返回JSON格式：
{{
  "shoes": {{"name": "", "features": [], "reason": ""}},
  "clothing": {{"top": "", "bottom": "", "reason": ""}},
  "gear": [{{"item": "", "priority": "essential|recommended", "reason": ""}}],
  "nutrition": [{{"item": "", "timing": "", "amount": ""}}]
}}"""
        
        resp = requests.post(
            self.endpoint,
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': self.model,
                'messages': [
                    {'role': 'system', 'content': '你是越野跑装备专家，返回严格JSON。所有内容必须用中文。'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.7,
                'max_tokens': 1500
            },
            timeout=30
        )
        
        if resp.status_code != 200:
            return self._default_equipment(route_data)
        
        content = resp.json()['choices'][0]['message']['content']
        content = self._clean_json(content)
        
        try:
            return json.loads(content)
        except:
            return self._default_equipment(route_data)
    
    def local_plan(self, params: dict) -> dict:
        """Local fallback training plan when AI is unavailable."""
        weeks = params.get('weeks', 12)
        target = params.get('target_distance', 50)
        level = params.get('level', 'intermediate')
        
        base_dist = 30 if level == 'beginner' else 50 if level == 'intermediate' else 70
        
        schedule = []
        for w in range(1, weeks + 1):
            if w <= 4:
                phase, focus = '基础期', '建立有氧基础'
                dist = int(base_dist * (0.8 + w * 0.05))
            elif w <= 8:
                phase, focus = '提升期', '提升乳酸阈值'
                dist = int(base_dist * (1.0 + (w-4) * 0.03))
            elif w <= weeks - 2:
                phase, focus = '强化期', '模拟赛事强度'
                dist = int(base_dist * 1.15)
            else:
                phase, focus = '减量期', '恢复调整'
                dist = int(base_dist * (0.9 - (w - (weeks-2)) * 0.25))
            
            long_run = int(dist * 0.35)
            
            schedule.append({
                'week': w,
                'phase': phase,
                'total_distance_km': dist,
                'focus': focus,
                'long_run_km': long_run,
                'workouts': [
                    {'day': '周一', 'type': '休息', 'description': '恢复或轻度拉伸', 'duration': '-'},
                    {'day': '周二', 'type': '轻松跑', 'description': f'{int(dist*0.15)}km轻松跑', 'duration': f'{int(dist*0.15*6)}分钟'},
                    {'day': '周三', 'type': '间歇训练', 'description': '变速训练', 'duration': '45分钟'},
                    {'day': '周四', 'type': '轻松跑', 'description': f'{int(dist*0.12)}km恢复跑', 'duration': f'{int(dist*0.12*6)}分钟'},
                    {'day': '周五', 'type': '休息', 'description': '完全休息', 'duration': '-'},
                    {'day': '周六', 'type': '长跑', 'description': f'{long_run}km长距离', 'duration': f'{int(long_run*7)}分钟'},
                    {'day': '周日', 'type': '轻松跑', 'description': f'{int(dist*0.1)}km恢复跑', 'duration': f'{int(dist*0.1*6)}分钟'}
                ]
            })
        
        return {
            'plan_name': f'{target}公里越野赛备战计划',
            'duration_weeks': weeks,
            'target_distance': target,
            'weekly_schedule': schedule,
            'note': 'AI服务暂时不可用，已自动切换本地算法生成'
        }
    
    def _build_plan_prompt(self, params: dict) -> str:
        """Build prompt for training plan generation."""
        weeks = params.get('weeks', 12)
        target = params.get('target_distance', 50)
        level = params.get('level', 'intermediate')
        weekly = params.get('weekly_distance', 40)
        
        level_cn = {'beginner': '入门', 'intermediate': '中级', 'advanced': '高级'}.get(level, level)
        
        return f"""请为一名{level_cn}水平跑者制定{weeks}周{target}公里越野跑训练计划。
当前周跑量约{weekly}公里。
要求：
1. 返回严格JSON，不要任何Markdown标记，不要任何解释性文字
2. 所有内容必须用中文
3. 包含weekly_schedule数组，每周必须有7天
4. 每天包含：day, type, description, duration
5. 训练类型包括：休息、轻松跑、间歇训练、节奏跑、长跑、山地训练、力量训练
6. 赛前2周开始减量，最后一周跑量降到平时的50%
7. plan_name 用中文
8. phase 和 focus 用中文

JSON格式：
{{
"plan_name": "{target}公里越野赛备战计划",
"duration_weeks": {weeks},
"target_distance": {target},
"weekly_schedule": [
{{
"week": 1,
"phase": "基础期",
"total_distance_km": 40,
"focus": "建立基础",
"workouts": [
{{"day": "周一", "type": "休息", "description": "完全休息", "duration": "-"}},
{{"day": "周二", "type": "轻松跑", "description": "8km轻松跑", "duration": "50分钟"}},
{{"day": "周三", "type": "间歇训练", "description": "6x800m间歇", "duration": "45分钟"}},
{{"day": "周四", "type": "轻松跑", "description": "6km恢复跑", "duration": "40分钟"}},
{{"day": "周五", "type": "休息", "description": "完全休息", "duration": "-"}},
{{"day": "周六", "type": "长跑", "description": "15km长距离", "duration": "1.5小时"}},
{{"day": "周日", "type": "轻松跑", "description": "5km恢复", "duration": "35分钟"}}
]
}}
]
}}"""
    
    def _clean_json(self, content: str) -> str:
        """Clean JSON content from markdown wrappers."""
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        return content.strip()
    
    def _default_equipment(self, route_data: dict = None) -> dict:
        """Default equipment recommendations with Chinese brands."""
        metrics = route_data.get('metrics', {}) if route_data else {}
        distance = metrics.get('total_distance_km', 50)
        
        # Determine if headlamp is needed based on distance
        # Short daytime runs don't need headlamp
        need_headlamp = distance > 30
        
        gear = [
            {'item': '水袋背包（5-10L）', 'priority': 'essential', 'reason': '长距离补水必备，推荐Salomon Advanced Skin或凯乐石飞翼'},
            {'item': '登山杖', 'priority': 'recommended', 'reason': '爬升路段省力，推荐LEKI或Black Diamond'},
            {'item': '急救包', 'priority': 'essential', 'reason': '应急处理，含绷带、碘伏、止痛药'}
        ]
        
        if need_headlamp:
            gear.insert(2, {'item': '头灯', 'priority': 'essential', 'reason': f'{distance}km长距离，需备用光源'})
        
        return {
            'shoes': {
                'name': 'Salomon Speedcross 6 / HOKA Speedgoat 5 / 凯乐石 Fuga DU',
                'features': ['Vibram Megagrip大底', '防碎石鞋套', '4-8mm落差'],
                'reason': '提供良好抓地力和足部保护，适合技术性越野路面'
            },
            'clothing': {
                'top': '美利奴羊毛速干长袖或轻量防风夹克',
                'bottom': '轻量越野短裤或压缩裤',
                'reason': '适应多变天气，快速排汗，减少摩擦'
            },
            'gear': gear,
            'nutrition': [
                {'item': '能量胶（SIS/ Maurten/ 康比特）', 'timing': '每45-60分钟', 'amount': f'{max(2, int(distance/10))}支'},
                {'item': '电解质饮料或盐丸', 'timing': '全程', 'amount': '500ml/小时'},
                {'item': '能量棒或坚果', 'timing': '后半程', 'amount': '1-2份'}
            ]
        }
