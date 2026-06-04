from apps.cards.models import Card, AssistantFilter, CardStatus
from typing import Optional

class CardSelector:
    @staticmethod
    def get_card(card_id: str) -> Optional[Card]:
        return Card.objects.filter(id=card_id).first()

    @staticmethod
    def get_table_cards(table_id: str, assistant=None):
        queryset = Card.objects.filter(table_id=table_id, status=CardStatus.ACTIVE)
        
        if assistant:
            # Apply assistant filters
            filters = AssistantFilter.objects.filter(assistant=assistant, table_id=table_id)
            for f in filters:
                for field_id, allowed_values in f.criteria.items():
                    # JSONB query: data__<field_id>__in=allowed_values
                    # For SQLite compatibility in tests, this might be tricky, but typically data__field_id__in is supported in JSONField
                    kwargs = {f"data__{field_id}__in": allowed_values}
                    queryset = queryset.filter(**kwargs)
                    
        return queryset

    @staticmethod
    def global_search(organization_id: str, query: str):
        # Global Search must search: Cards only
        # We can do a basic search across the JSON data values
        # Since JSON values can be anywhere, we can use __icontains on the data field or a specific field.
        # But global search usually means searching display_id or any field value
        # In Postgres, we could do full text search. For now, simple text matching.
        from django.db.models import Q
        return Card.objects.filter(
            Q(display_id__icontains=query) | Q(data__icontains=query),
            organization_id=organization_id,
            status=CardStatus.ACTIVE
        )
