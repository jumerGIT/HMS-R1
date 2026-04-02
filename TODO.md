# House Inventory Fix TODO

## Status: In Progress

### 1. [x] Update housing/views.py
- Annotate house_list queryset with effective_status ✓
- Update dashboard counts to use effective_status queries ✓
- Update house_detail_json to compute effective_status ✓

### 2. [x] Update housing/templates/housing/house_list.html ✓

### 3. [ ] Update dashboard templates

### 3. [ ] Update dashboard templates
- housing/templates/housing/dashboard_admin.html 
- housing/templates/housing/dashboard_housing.html

### 4. [x] Create management command housing/management/commands/fix_house_status.py ✓

### 5. [ ] Test & migrate
- python manage.py makemigrations
- python manage.py migrate  
- python manage.py fix_house_status
- Test house_list page

**Next step:** Implement views.py updates
