def farm_profile_completed_check(farm):
    print(f'provera kopetiranja profila farme: {len(farm.farm_description) > 100} i {farm.farm_image != "default.jpg"}')
    if len(farm.farm_description) > 100 and farm.farm_image != 'default.jpg':
        farm_profile_completed = True
    else:
        farm_profile_completed = False
    return farm_profile_completed