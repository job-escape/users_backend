from django.core import paginator
from django.utils.functional import cached_property


class NullPaginator(paginator.Paginator):

    def __init__(self, object_list, per_page: int | str, orphans: int, allow_empty_first_page: bool) -> None:
        super().__init__(object_list, per_page, orphans, allow_empty_first_page)
        self.per_page = 1

    @cached_property
    def count(self):
        return 0
