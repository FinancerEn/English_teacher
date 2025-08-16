from aiogram import Bot
from typing import List


class CustomBot(Bot):
    """
    Кастомный класс бота с дополнительными атрибутами
    """
    
    def __init__(self, token: str, **kwargs):
        super().__init__(token, **kwargs)
        self.my_admins_list: List[int] = []
    
    async def is_admin(self, user_id: int) -> bool:
        """
        Проверяет, является ли пользователь администратором
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если пользователь админ, False иначе
        """
        return user_id in self.my_admins_list
    
    def add_admin(self, user_id: int) -> None:
        """
        Добавляет пользователя в список администраторов
        
        Args:
            user_id: ID пользователя
        """
        if user_id not in self.my_admins_list:
            self.my_admins_list.append(user_id)
    
    def remove_admin(self, user_id: int) -> None:
        """
        Удаляет пользователя из списка администраторов
        
        Args:
            user_id: ID пользователя
        """
        if user_id in self.my_admins_list:
            self.my_admins_list.remove(user_id) 