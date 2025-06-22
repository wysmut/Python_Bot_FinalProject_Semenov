from enum import Enum

class AdStatus(Enum):
    DRAFT = 'draft'
    MODERATION = 'moderation'
    ACTIVE = 'active'
    REJECTED = 'rejected'

class ReviewType(Enum):
    BOT = 'bot'
    AD = 'ad'
    CONTENT = 'content'