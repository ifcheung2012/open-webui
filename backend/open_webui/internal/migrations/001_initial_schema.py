"""Peewee migrations -- 001_initial_schema.py.

OpenWebUI 数据库初始模式定义迁移文件。
本文件定义了系统最基础的数据表结构，作为数据库迁移的第一步。

以下是迁移器(migrator)的一些示例用法:

    > Model = migrator.orm['table_name']            # 通过表名返回当前状态的模型
    > Model = migrator.ModelClass                   # 通过模型类名返回当前状态的模型

    > migrator.sql(sql)                             # 运行自定义SQL
    > migrator.run(func, *args, **kwargs)           # 用给定参数运行Python函数
    > migrator.create_model(Model)                  # 创建模型(可用作装饰器)
    > migrator.remove_model(model, cascade=True)    # 删除模型
    > migrator.add_fields(model, **fields)          # 向模型添加字段
    > migrator.change_fields(model, **fields)       # 更改字段
    > migrator.remove_fields(model, *field_names, cascade=True)
    > migrator.rename_field(model, old_field_name, new_field_name)
    > migrator.rename_table(model, new_table_name)
    > migrator.add_index(model, *col_names, unique=False)
    > migrator.add_not_null(model, *field_names)
    > migrator.add_default(model, field_name, default)
    > migrator.add_constraint(model, name, sql)
    > migrator.drop_index(model, *col_names)
    > migrator.drop_not_null(model, *field_names)
    > migrator.drop_constraints(model, *constraints)

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """
    数据库迁移的主入口函数。
    
    根据数据库类型选择不同的迁移策略：
    - 对于SQLite数据库：使用专门的SQLite迁移函数
    - 对于外部数据库(如PostgreSQL)：使用专门的外部数据库迁移函数
    
    参数:
        migrator: Peewee迁移器对象
        database: 数据库连接实例
        fake: 是否模拟迁移而不实际执行
    """

    # 为SQLite和其他数据库执行不同的迁移
    # 这是因为SQLite在模式强制执行方面非常宽松，尝试像SQLite一样迁移其他数据库
    # 需要针对每个数据库的SQL查询。
    # 相反，由于外部数据库支持是在后期添加的，我们假设较新的基础
    # 模式，而不是尝试从旧模式迁移。
    if isinstance(database, pw.SqliteDatabase):
        migrate_sqlite(migrator, database, fake=fake)
    else:
        migrate_external(migrator, database, fake=fake)


def migrate_sqlite(migrator: Migrator, database: pw.Database, *, fake=False):
    """
    SQLite数据库的迁移函数，创建基础表结构。
    
    为SQLite数据库创建初始表结构，包括用户认证、聊天、标签等核心功能所需的表。
    
    参数:
        migrator: Peewee迁移器对象
        database: 数据库连接实例
        fake: 是否模拟迁移而不实际执行
    """
    @migrator.create_model
    class Auth(pw.Model):
        """用户认证表，存储用户登录凭证"""
        id = pw.CharField(max_length=255, unique=True)
        email = pw.CharField(max_length=255)
        password = pw.CharField(max_length=255)
        active = pw.BooleanField()

        class Meta:
            table_name = "auth"

    @migrator.create_model
    class Chat(pw.Model):
        """聊天记录表，存储用户与AI的对话内容"""
        id = pw.CharField(max_length=255, unique=True)
        user_id = pw.CharField(max_length=255)
        title = pw.CharField()
        chat = pw.TextField()
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "chat"

    @migrator.create_model
    class ChatIdTag(pw.Model):
        """聊天标签关联表，用于管理聊天记录的标签"""
        id = pw.CharField(max_length=255, unique=True)
        tag_name = pw.CharField(max_length=255)
        chat_id = pw.CharField(max_length=255)
        user_id = pw.CharField(max_length=255)
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "chatidtag"

    @migrator.create_model
    class Document(pw.Model):
        """文档表，存储用于检索增强生成(RAG)的文档"""
        id = pw.AutoField()
        collection_name = pw.CharField(max_length=255, unique=True)
        name = pw.CharField(max_length=255, unique=True)
        title = pw.CharField()
        filename = pw.CharField()
        content = pw.TextField(null=True)
        user_id = pw.CharField(max_length=255)
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "document"

    @migrator.create_model
    class Modelfile(pw.Model):
        """模型文件表，存储Ollama模型定义文件"""
        id = pw.AutoField()
        tag_name = pw.CharField(max_length=255, unique=True)
        user_id = pw.CharField(max_length=255)
        modelfile = pw.TextField()
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "modelfile"

    @migrator.create_model
    class Prompt(pw.Model):
        """提示词表，存储预定义的提示模板"""
        id = pw.AutoField()
        command = pw.CharField(max_length=255, unique=True)
        user_id = pw.CharField(max_length=255)
        title = pw.CharField()
        content = pw.TextField()
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "prompt"

    @migrator.create_model
    class Tag(pw.Model):
        """标签表，存储用户创建的标签"""
        id = pw.CharField(max_length=255, unique=True)
        name = pw.CharField(max_length=255)
        user_id = pw.CharField(max_length=255)
        data = pw.TextField(null=True)

        class Meta:
            table_name = "tag"

    @migrator.create_model
    class User(pw.Model):
        """用户表，存储用户基本信息"""
        id = pw.CharField(max_length=255, unique=True)
        name = pw.CharField(max_length=255)
        email = pw.CharField(max_length=255)
        role = pw.CharField(max_length=255)
        profile_image_url = pw.CharField(max_length=255)
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "user"


def migrate_external(migrator: Migrator, database: pw.Database, *, fake=False):
    """
    外部数据库(如PostgreSQL)的迁移函数，创建基础表结构。
    
    为外部数据库创建初始表结构，与SQLite版本相似，但字段类型有所调整以适应外部数据库特性。
    
    参数:
        migrator: Peewee迁移器对象
        database: 数据库连接实例
        fake: 是否模拟迁移而不实际执行
    """
    @migrator.create_model
    class Auth(pw.Model):
        """用户认证表，存储用户登录凭证"""
        id = pw.CharField(max_length=255, unique=True)
        email = pw.CharField(max_length=255)
        password = pw.TextField()  # 注意：这里使用TextField而不是CharField
        active = pw.BooleanField()

        class Meta:
            table_name = "auth"

    @migrator.create_model
    class Chat(pw.Model):
        """聊天记录表，存储用户与AI的对话内容"""
        id = pw.CharField(max_length=255, unique=True)
        user_id = pw.CharField(max_length=255)
        title = pw.TextField()  # 使用TextField以支持更长的标题
        chat = pw.TextField()
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "chat"

    @migrator.create_model
    class ChatIdTag(pw.Model):
        """聊天标签关联表，用于管理聊天记录的标签"""
        id = pw.CharField(max_length=255, unique=True)
        tag_name = pw.CharField(max_length=255)
        chat_id = pw.CharField(max_length=255)
        user_id = pw.CharField(max_length=255)
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "chatidtag"

    @migrator.create_model
    class Document(pw.Model):
        """文档表，存储用于检索增强生成(RAG)的文档"""
        id = pw.AutoField()
        collection_name = pw.CharField(max_length=255, unique=True)
        name = pw.CharField(max_length=255, unique=True)
        title = pw.TextField()  # 使用TextField以支持更长的标题
        filename = pw.TextField()  # 使用TextField以支持更长的文件名
        content = pw.TextField(null=True)
        user_id = pw.CharField(max_length=255)
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "document"

    @migrator.create_model
    class Modelfile(pw.Model):
        """模型文件表，存储Ollama模型定义文件"""
        id = pw.AutoField()
        tag_name = pw.CharField(max_length=255, unique=True)
        user_id = pw.CharField(max_length=255)
        modelfile = pw.TextField()
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "modelfile"

    @migrator.create_model
    class Prompt(pw.Model):
        """提示词表，存储预定义的提示模板"""
        id = pw.AutoField()
        command = pw.CharField(max_length=255, unique=True)
        user_id = pw.CharField(max_length=255)
        title = pw.TextField()  # 使用TextField以支持更长的标题
        content = pw.TextField()
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "prompt"

    @migrator.create_model
    class Tag(pw.Model):
        """标签表，存储用户创建的标签"""
        id = pw.CharField(max_length=255, unique=True)
        name = pw.CharField(max_length=255)
        user_id = pw.CharField(max_length=255)
        data = pw.TextField(null=True)

        class Meta:
            table_name = "tag"

    @migrator.create_model
    class User(pw.Model):
        """用户表，存储用户基本信息"""
        id = pw.CharField(max_length=255, unique=True)
        name = pw.CharField(max_length=255)
        email = pw.CharField(max_length=255)
        role = pw.CharField(max_length=255)
        profile_image_url = pw.TextField()  # 使用TextField以支持更长的URL
        timestamp = pw.BigIntegerField()

        class Meta:
            table_name = "user"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """
    回滚迁移的函数，按照相反的顺序删除所有创建的表。
    
    当需要撤销此迁移时，按照依赖关系的反序删除所有表。
    
    参数:
        migrator: Peewee迁移器对象
        database: 数据库连接实例
        fake: 是否模拟回滚而不实际执行
    """

    migrator.remove_model("user")

    migrator.remove_model("tag")

    migrator.remove_model("prompt")

    migrator.remove_model("modelfile")

    migrator.remove_model("document")

    migrator.remove_model("chatidtag")

    migrator.remove_model("chat")

    migrator.remove_model("auth")
