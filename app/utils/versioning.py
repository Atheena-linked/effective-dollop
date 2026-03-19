async def get_next_version(collection, patient_id:str):
    count = await collection.count_documents({
        "patient_id" :patient_id
    })
    return count + 1 #this is the next version number that will be assigned to the next entry