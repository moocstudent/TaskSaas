# Create your views here.
import random

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django_redis import get_redis_connection

from utils.tencent.sms import send_sms_single

from web import models
from django.core.validators import RegexValidator
from utils import encrypt
from web.forms.bootstrap import BootStrapForm


class RegisterModelForm(BootStrapForm, forms.ModelForm):
    """
    注册表单自动生成
    """
    password = forms.CharField(label='密码', min_length=6, max_length=18, error_messages={
        'min_length': '密码长度不能小于6个字符',
        'max_length': '密码长度不能大于18个字符'
    }, widget=forms.PasswordInput())

    confirm_password = forms.CharField(label='重复密码', min_length=6, max_length=18, error_messages={
        'min_length': '重复密码长度不能小于6个字符',
        'max_length': '重复密码长度不能大于18个字符'
    }, widget=forms.PasswordInput())
    # mobile_phone = forms.CharField(label='手机号码',
    #                                validators=[RegexValidator(r'^(1[3|4|5|6|7|8|9])\d{9}$', '手机号码格式错误'), ])

    # code = forms.CharField(label='验证码', widget=forms.TextInput())

    class Meta:
        model = models.UserInfo
        fields = ['username', 'email', 'password', 'confirm_password' ]

    def clean_username(self):
        username = self.cleaned_data['username']
        exists = models.UserInfo.objects.filter(username=username).exists()
        if exists:
            raise ValidationError('用户名已存在')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        exists = models.UserInfo.objects.filter(email=email).exists()
        if exists:
            raise ValidationError('邮箱已存在')
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        # 加密 & 返回
        return encrypt.md5(password)

    def clean_confirm_password(self):
        password = self.cleaned_data['password']
        confirm_password = encrypt.md5(self.cleaned_data['confirm_password'])
        if password != confirm_password:
            raise ValidationError("两次密码不一致！")
        return confirm_password

    # def clean_mobile_phone(self):
    #     mobile_phone = self.cleaned_data['mobile_phone']
    #     exists = models.UserInfo.objects.filter(mobile_phone=mobile_phone).exists()
    #     if exists:
    #         raise ValidationError('手机号已注册')
    #     return mobile_phone

    # def clean_code(self):
    #     code = self.cleaned_data['code']
    #     mobile_phone = self.cleaned_data.get('mobile_phone')
    #     if not mobile_phone:
    #         return code
    #
    #     conn = get_redis_connection()
    #     redis_code = conn.get(mobile_phone)
    #     if not redis_code:
    #         raise ValidationError('验证码已过期！')
    #
    #     redis_str_code = redis_code.decode('utf-8')
    #
    #     if code.strip() != redis_str_code:
    #         raise ValidationError('验证码错误！')
    #     return code


class SendSmsForm(forms.Form):
    """
    发送短信
    """
    mobile_phone = forms.CharField(label='手机号码',
                                   validators=[RegexValidator(r'^(1[3|4|5|6|7|8|9])\d{9}$', '手机号码格式错误'), ])

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request

    def clean_mobile_phone(self):
        """手机号码校验的钩子"""
        mobile_phone = self.cleaned_data['mobile_phone']
        # 判断短信模板是否有问题
        tpl = self.request.GET.get('tpl')
        template_id = settings.TENCENT_SMS_TEMPLATES.get(tpl)
        if not template_id:
            raise ValidationError('短信模板错误')

        exists = models.UserInfo.objects.filter(mobile_phone=mobile_phone).exists()

        code = random.randrange(1000, 9999)
        # 校验数据库中是否有该号码
        # 发短信 & 写redis
        if tpl == 'login':
            if not exists:
                raise ValidationError('手机号码不存在')
            sms = send_sms_single(mobile_phone, template_id, [code, 1])
        else:
            if exists:
                raise ValidationError('手机号码已存在')
            sms = send_sms_single(mobile_phone, template_id, [code, ])

        if sms['result'] != 0:
            raise ValidationError('短信发送失败, {}'.format(sms['errmsg']))

        # 验证码写入redis(使用django-redis)
        conn = get_redis_connection("default")
        conn.set(mobile_phone, code, ex=60)

        return mobile_phone


class LoginSmsForm(BootStrapForm, forms.Form):
    """
    短信登陆表单生成
    """
    mobile_phone = forms.CharField(label='手机号码',
                                   validators=[RegexValidator(r'^(1[3|4|5|6|7|8|9])\d{9}$', '手机号码格式错误'), ])

    # code = forms.CharField(label='验证码', widget=forms.TextInput())

    # def clean_mobile_phone(self):
    #     mobile_phone = self.cleaned_data['mobile_phone']
    #     user_object = models.UserInfo.objects.filter(mobile_phone=mobile_phone).first()
    #     if not user_object:
    #         raise ValidationError('手机号码不存在')
    #     return user_object

    # def clean_code(self):
    #     code = self.cleaned_data['code']
    #     user_object = self.cleaned_data.get('mobile_phone')
    #     # 手机号不存在，验证码无需校验
    #     if not user_object:
    #         return code
    #
    #     conn = get_redis_connection()
    #     redis_code = conn.get(user_object.mobile_phone)
    #
    #     if not redis_code:
    #         raise ValidationError('验证码失效，请重新发送！')
    #
    #     redis_str_code = redis_code.decode('utf-8')
    #
    #     if code.strip() != redis_str_code:
    #         raise ValidationError('验证码错误，请重新输入！')
    #
    #     return code


class LoginForm(BootStrapForm, forms.Form):
    """
    密码登陆表单生成
    """
    username = forms.CharField(label='邮箱或用户名')
    password = forms.CharField(label='密码', widget=forms.PasswordInput())
    # code = forms.CharField(label='图片验证码')

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request

    def clean_password(self):
        password = self.cleaned_data['password']
        return encrypt.md5(password)

    # def clean_code(self):
    #     """
    #     校验图片验证码
    #     :return:
    #     """
    #     code = self.cleaned_data['code']
    #     session_code = self.request.session.get('image_code')
    #     if not session_code:
    #         raise ValidationError("验证码已过期，请重试！")
    #
    #     if code.strip().upper() != session_code.upper():
    #         raise ValidationError('验证码错误，请重试！')
    #
    #     return code
