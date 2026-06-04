from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from apps.cards.serializers import CardSerializer
from apps.cards.services import CardService, StaleWriteError
from apps.cards.selectors import CardSelector
from apps.cards.policies import CardPolicy
from apps.tables.selectors import TableSelector
from shared.constants import Role
from rest_framework.exceptions import ValidationError

class CardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def create(self, request):
        if not CardPolicy.can_manage_cards(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
            
        table_id = request.data.get('table_id')
        data = request.data.get('data', {})
        
        table = TableSelector.get_table(table_id)
        if not table:
            return Response({'error': 'Table not found'}, status=status.HTTP_404_NOT_FOUND)
            
        try:
            card = CardService.create_card(table, str(table.organization_id), data, created_by=request.user)
            return Response(CardSerializer(card).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def list(self, request):
        table_id = request.query_params.get('table_id')
        
        # Resolve assistant context
        assistant = None
        if request.user.role == Role.ASSISTANT:
            assistant = request.user
            
        cards = CardSelector.get_table_cards(table_id, assistant=assistant)
        return Response(CardSerializer(cards, many=True).data)
        
    def partial_update(self, request, pk=None):
        if not CardPolicy.can_manage_cards(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
            
        card = CardSelector.get_card(pk)
        if not card:
            return Response({'error': 'Card not found'}, status=status.HTTP_404_NOT_FOUND)
            
        data_update = request.data.get('data', {})
        expected_version = request.data.get('version')
        
        if expected_version is None:
            return Response({'error': 'version is required for optimistic locking'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            updated_card = CardService.update_card(card, data_update, int(expected_version), updated_by=request.user)
            return Response(CardSerializer(updated_card).data)
        except StaleWriteError as e:
            return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        organization_id = request.query_params.get('organization_id')
        
        cards = CardSelector.global_search(organization_id, query)
        return Response(CardSerializer(cards, many=True).data)
