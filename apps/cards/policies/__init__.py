from shared.constants import Role

class CardPolicy:
    @staticmethod
    def can_manage_cards(user) -> bool:
        # Assistants can manage cards within their filters
        return user.role in [Role.PRO_USER, Role.ADMIN, Role.CLIENT, Role.ASSISTANT]
