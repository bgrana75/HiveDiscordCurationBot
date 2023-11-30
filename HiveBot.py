import os
import discord
from discord.ext import tasks
from dotenv import load_dotenv
from supabase import create_client
from beem import Hive
from beem.account import Account
from beem.comment import Comment
from beem.utils import resolve_authorperm, construct_authorperm
from beem.instance import set_shared_blockchain_instance

load_dotenv()

discordToken = os.environ.get("DISCORD_TOKEN")
discordAdmin = os.environ.get("DISCORD_ADMIN_ID")

supabaseURL = os.environ.get("SUPABASE_URL")
supabaseKEY = os.environ.get("SUPABASE_KEY")
dbQueueTable = "curation_queue"
dbCuratorsTable = "curation_curators"
supabase = create_client(supabaseURL, supabaseKEY)

curationAccountName = os.environ.get("CURATION_ACCOUNT")
curationAccountPostingKey = os.environ.get("CURATION_POSTING_KEY")
hive = Hive(node=['https://api.hive.blog'], keys={'posting':curationAccountPostingKey})
set_shared_blockchain_instance(hive)

intents = discord.Intents.all()
client = discord.Client(command_prefix='!', intents=intents)

def isCurator(message):
    discordUserId = message.author.id
    checkUser = supabase.table(dbCuratorsTable).select("*", count="exact").eq("discord_id", discordUserId).execute()
    if checkUser.count == 0:
        return False
    else:
        return True
 
@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))
    myLoop.start()
 
@client.event
async def on_message(message):
    if message.author == client.user:
        return
 
    if message.content.startswith('hi'):
        await message.channel.send(message.author)

    if message.content.startswith('addcurator'):
        if (str(message.author.id) == discordAdmin):
            params = message.content.split()
            discordUserId = message.mentions[0].id
            hiveUser = params[2]
            checkUser = supabase.table(dbCuratorsTable).select("*", count="exact").eq("discord_id", discordUserId).execute()
            if checkUser.count == 0:
                supabase.table(dbCuratorsTable).insert({"discord_id": discordUserId, "hive_id": hiveUser}).execute()
                responseText = "User: <@" + str(discordUserId) + "> added to curation list"      
                await message.channel.send(responseText)
            else:
                await message.channel.send("Error: Discord user is already a curator")
        else:
            await message.channel.send("Not Authorized")

    if message.content.startswith('listcurators'):
        if (str(message.author.id) == discordAdmin):
            result = supabase.table(dbCuratorsTable).select("*").execute().data
            responseText = 'Curators List:\n>>> '
            for curator in result:
                responseText = responseText + "discord: <@" + str(curator["discord_id"]) + ">" + " => Hive: @" + str(curator["hive_id"]) + '\n'
                
            await message.channel.send(responseText)
            return
        else:
            await message.channel.send("Not Authorized")
            return
    
    if message.content.startswith('removecurator'):
        if (str(message.author.id) == discordAdmin):
            discordUserId = message.mentions[0].id
            checkUser = supabase.table(dbCuratorsTable).select("*", count="exact").eq("discord_id", discordUserId).execute()
            if checkUser.count == 0:
                await message.channel.send("This user is not a curator")
            else:
                result = supabase.table(dbCuratorsTable).delete().eq("discord_id", discordUserId).execute()
                responseText = "User: <@" + str(discordUserId) + "> removed from curation list"
                await message.channel.send(responseText)
            return
        else:
            await message.channel.send("Not Authorized")
            return

    if message.content.startswith('upvote'):
        if not isCurator(message):
            await message.channel.send("Not Authorized!")
            return

        params = message.content.split()
        try:
            author, permlink = resolve_authorperm(params[1])
            authorperm = construct_authorperm(author, permlink)
            checkLink = supabase.table(dbQueueTable).select("*", count="exact").eq("link", authorperm).execute()
            if checkLink.count == 0:
                c = Comment(authorperm)
                voteWeight = params[2]
                supabase.table(dbQueueTable).insert({"curator": message.author.id,"link": authorperm, "vote_weight": voteWeight, "post_created": str(c["created"]), "status": "waiting"}).execute()
                await message.channel.send(type(c["created"]))
            else:
                await message.channel.send("Post already in queue!")
        except:
            await message.channel.send("Invalid Link!")
 
    if message.content.startswith('removepost'):
        if not isCurator(message):
            await message.channel.send("Not Authorized!")
            return

        params = message.content.split()
        try:
            author, permlink = resolve_authorperm(params[1])
            authorperm = construct_authorperm(author, permlink)
            checkLink = supabase.table(dbQueueTable).select("*", count="exact").eq("link", authorperm).execute()
            if checkLink.count == 0:
               await message.channel.send("This link is not in queue")
            else:
                result = supabase.table(dbQueueTable).delete().eq("link", authorperm).execute()
                responseText = "Link removed from queue successfully"
                await message.channel.send(responseText)
            return
        except:
            await message.channel.send("Invalid Link!")
        
    if message.content.startswith('showqueue'):
        if not isCurator(message):
            await message.channel.send("Not Authorized!")
            return

        result = supabase.table(dbQueueTable).select("*").eq("status", "waiting").order("post_created").execute().data
        responseText = 'Posts List:\n>>> '
        for post in result:
            responseText = responseText + "Post: " + str(post["link"]) + '\n'
        await message.channel.send(responseText)
        return

@tasks.loop(seconds = 60)
async def myLoop():
    curationAccount = Account(curationAccountName)
    if curationAccount.get_voting_power() <= 80:
        post = supabase.table(dbQueueTable).select("*").eq("status", "waiting").order("post_created").execute().data[0]
        try:
            return
            #c = Comment(post["link"])
            #c.upvote(post["vote_weight"], voter=curationAccountName)
            #supabase.table(dbQueueTable).update({"status": "upvoted"}).eq("id", post["id"]).execute()
        except:
            return

        print(curationAccount.get_voting_power())
 
client.run(discordToken)