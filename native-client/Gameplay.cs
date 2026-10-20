using System;
using System.IO;
using System.Linq;
using System.Drawing;
using System.Drawing.Imaging;
using System.Collections.Generic;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace CoreLicht {
public partial class ClientWindow {
    readonly Timer gameTimer=new Timer();
    Dictionary<string,object> gameState,battle;
    int selectedRoleId,chosenStage=10001;
    string deployChoice="",startRequest="";
    bool gameBusy;
    void SetupGameplay(){
        gameTimer.Interval=400;
        gameTimer.Tick+=async(s,e)=>{if(screen=="Battle"&&!gameBusy&&notice.Length==0)await GameCommand("state",Data.Obj());};
        if(!smoke)gameTimer.Start();FormClosed+=(s,e)=>gameTimer.Dispose();
    }
    async Task<bool> GameCommand(string command,Dictionary<string,object> values){
        if(gameBusy||connection==null)return false;gameBusy=true;
        try{
            gameState=await connection.Gameplay(command,selectedRoleId,values);
            if(IsDisposed)return false;
            battle=gameState["battle"]==null?null:Data.Map(gameState["battle"]);
            var stamina=Data.Map(gameState["vitality"]);energy=Data.Text(stamina["vitality"]);energyMax=Data.Text(stamina["vit_max"]);
            if(screen=="Battle"&&battle!=null&&Data.Text(battle["status"])!="active")Navigate("Result");
            return true;
        }catch(Exception ex){notice="操作未完成："+ex.Message;if(smoke)throw;return false;}
        finally{gameBusy=false;if(!IsDisposed)gameView.Invalidate();}
    }
    string BattleStatus {get{return battle==null?"":Data.Text(battle["status"]);}}
    bool HasPendingBattle {get{return battle!=null&&BattleStatus!="claimed";}}
    Dictionary<string,object> Progress {get{return gameState==null?Data.Obj("points",0,"clears",Data.Obj(),"victories",0):Data.Map(gameState["progress"]);}}
    async Task BeginBattle(){
        if(HasPendingBattle){Navigate(BattleStatus=="active"?"Battle":"Result");return;}
        if(startRequest.Length==0)startRequest=Guid.NewGuid().ToString("N");
        if(await GameCommand("start",Data.Obj("stage",chosenStage,"request_id",startRequest))){
            startRequest="";deployChoice="";Navigate(BattleStatus=="active"?"Battle":"Result");
        }
    }
    async Task Deploy(int x,int y){
        if(deployChoice.Length==0){notice="先選擇下方隊員，再點選左側部署區。";return;}
        if(battle==null||gameBusy)return;
        if(await GameCommand("deploy",Data.Obj("battle_id",battle["id"],"card_id",deployChoice,"x",x,"y",y)))deployChoice="";
    }
    async Task QuickDeploy(){
        if(battle==null||gameBusy)return;
        var choices=Data.Items(battle["roster"]).Select(Data.Map).Where(c=>!Convert.ToBoolean(c["deployed"])).Take(3).ToList();
        int i=0;foreach(var card in choices){if(BattleStatus!="active")break;deployChoice=Data.Text(card["id"]);await Deploy(5,1+(i++*2));}
    }
    async Task SettleBattle(){if(battle!=null&&await GameCommand("claim",Data.Obj("battle_id",battle["id"])))Navigate("Stages");}
    void DrawStages(Graphics g){
        TextAt(g,"作戰演習",64,Cream,250,140,1200,110);
        TextAt(g,"選擇關卡與隊伍，部署適格體完成演習。",31,Color.White,250,255,1500,70);
        TextAt(g,"演習點數  "+Data.Text(Progress["points"])+"       精神力  "+energy+" / "+energyMax,33,Cream,250,350,1500,80);
        if(gameState==null){Button(g,"載入關卡",850,500,500,90,async()=>await GameCommand("state",Data.Obj()),true);return;}
        var clears=Data.Map(Progress["clears"]);int index=0;
        foreach(var entry in Data.Items(gameState["stages"])){var stage=Data.Map(entry);int id=(int)Data.Number(stage["id"]);
            int required=(int)Data.Number(stage["prerequisite"]);bool unlocked=required==0||clears.ContainsKey(required.ToString());
            float x=250+index*610,y=465;bool chosen=id==chosenStage;
            Rect(g,chosen?Color.FromArgb(200,141,128,86):Color.FromArgb(180,29,31,29),x,y,560,320);
            using(var pen=new Pen(chosen?Cream:Color.FromArgb(130,130,127),chosen?4:1))g.DrawRectangle(pen,x,y,560,320);
            TextAt(g,Data.Text(stage["number"]),65,unlocked?Cream:Color.Gray,x+35,y+15,490,100);
            TextAt(g,Data.Text(stage["name"]),34,Color.White,x+35,y+110,490,70);
            string rating=clears.ContainsKey(id.ToString())?new string('★',(int)Data.Number(clears[id.ToString()])):unlocked?"未通關":"尚未解鎖";
            TextAt(g,rating,32,unlocked?Cream:Color.Gray,x+35,y+190,490,55);
            TextAt(g,"精神力 "+Data.Text(stage["cost"])+"    演習點數 +"+Data.Text(stage["reward"]),26,Color.White,x+35,y+252,490,50);
            Hit(x,y,560,320,()=>{if(unlocked)chosenStage=id;else notice="先完成前一關演習。";});index++;
        }
        TextAt(g,"此為演習規則；原版技能、AI 與掉落仍在還原。",25,Color.FromArgb(190,Color.White),250,820,1800,65);
        Button(g,"調整編隊",250,935,310,90,()=>Navigate("Team"));
        Button(g,gameBusy?"連線中…":HasPendingBattle?"繼續作戰":"開始作戰",1770,935,420,90,async()=>await BeginBattle(),true);
    }
    static float Real(object value){return Convert.ToSingle(value,System.Globalization.CultureInfo.InvariantCulture);}
    void DrawBattle(Graphics g){
        if(battle==null){TextAt(g,"正在載入戰場…",42,Cream,600,400,1200,100,true);return;}
        const float left=250,top=170,tileW=100,tileH=92;
        Rect(g,Color.FromArgb(225,24,32,34),left-10,top-10,1420,664);
        for(int y=0;y<7;y++)for(int x=0;x<14;x++){
            int gx=x,gy=y;float px=left+x*tileW,py=top+y*tileH;
            Rect(g,x<=5?Color.FromArgb(90,85,118,123):Color.FromArgb(60,135,101,88),px+2,py+2,tileW-4,tileH-4);
            Line(g,Color.FromArgb(65,Cream),px,py,px+tileW,py,1);Line(g,Color.FromArgb(65,Cream),px,py,px,py+tileH,1);
            if(x<=5)Hit(px,py,tileW,tileH,async()=>await Deploy(gx,gy));
        }
        TextAt(g,"部署區",24,Color.FromArgb(130,Color.White),left+10,top+5,600,40);
        var units=Data.Items(battle["units"]).Select(Data.Map).ToList();
        if(battle.ContainsKey("last_hit")){var hit=Data.Map(battle["last_hit"]);if(Data.Number(battle["tick"])-Data.Number(hit["tick"])<=1){
            var a=units.FirstOrDefault(u=>Data.Text(u["id"])==Data.Text(hit["source"]));var b=units.FirstOrDefault(u=>Data.Text(u["id"])==Data.Text(hit["target"]));
            if(a!=null&&b!=null)Line(g,Cream,left+(Real(a["x"])+.5f)*tileW,top+(Real(a["y"])+.5f)*tileH,left+(Real(b["x"])+.5f)*tileW,top+(Real(b["y"])+.5f)*tileH,4);
        }}
        foreach(var unit in units.OrderBy(u=>Real(u["y"]))){
            float x=left+(Real(unit["x"])+.5f)*tileW,y=top+(Real(unit["y"])+.5f)*tileH;bool ally=Data.Text(unit["side"])=="ally";
            if(Data.Number(unit["hp"])<=0){TextAt(g,"×",35,Color.FromArgb(100,Color.White),x-20,y-20,40,40,true);continue;}
            if(ally){var card=cards.FirstOrDefault(c=>Data.Text(c["id"])==Data.Text(unit["id"]));FitArt(g,card==null?null:CardPortrait(card),new RectangleF(x-35,y-65,70,105));}
            else{using(var brush=new SolidBrush(Color.FromArgb(210,170,66,57)))g.FillPolygon(brush,new[]{new PointF(x,y-30),new PointF(x+27,y),new PointF(x,y+30),new PointF(x-27,y)});
                TextAt(g,"敵",25,Color.White,x-25,y-25,50,50,true);}
            Rect(g,Color.FromArgb(210,10,12,12),x-40,y+42,80,8);
            Rect(g,ally?Color.FromArgb(154,215,190):Color.FromArgb(231,125,108),x-40,y+42,80*Real(unit["hp"])/Real(unit["max_hp"]),8);
        }
        TextAt(g,"殲滅",30,Cream,1770,205,400,65);TextAt(g,Data.Text(battle["kills"])+" / "+Data.Text(battle["enemy_total"]),66,Color.White,1770,280,400,90);
        TextAt(g,"剩餘時間",30,Cream,1770,405,400,65);TextAt(g,Math.Max(0,60-Real(battle["tick"])*.25f).ToString("0.0")+" s",55,Color.White,1770,480,400,90);
        Button(g,"快速部署",1770,645,350,75,async()=>await QuickDeploy(),true);
        TextAt(g,"選擇下方隊員，再點左側部署區。",26,Cream,250,835,1500,60);
        int index=0;foreach(var entry in Data.Items(battle["roster"])){var member=Data.Map(entry);string id=Data.Text(member["id"]);bool used=Convert.ToBoolean(member["deployed"]);float x=250+index*205;
            Rect(g,used?Color.FromArgb(180,34,35,33):deployChoice==id?Color.FromArgb(210,160,142,92):Color.FromArgb(215,60,64,60),x,910,195,150);
            var card=cards.FirstOrDefault(c=>Data.Text(c["id"])==id);if(card!=null)FitArt(g,CardPortrait(card),new RectangleF(x+5,915,65,140));
            TextAt(g,card==null?id:CharacterName(card),25,used?Color.Gray:Cream,x+78,920,110,85);
            TextAt(g,used?"已部署":"選擇",22,used?Color.Gray:Color.White,x+78,1007,110,40);
            Hit(x,910,195,150,()=>{if(!used)deployChoice=id;});index++;
        }
        Button(g,"放棄演習",1950,950,245,70,async()=>{if(battle!=null&&await GameCommand("abandon",Data.Obj("battle_id",battle["id"])))Navigate("Stages");});
    }
    void DrawBattleResult(Graphics g){
        if(battle==null)return;string status=BattleStatus=="claimed"?Data.Text(battle["outcome"]):BattleStatus;bool won=status=="victory";
        Rect(g,Color.FromArgb(180,12,15,14),250,200,1870,670);
        TextAt(g,won?"作戰成功":status=="abandoned"?"演習結束":"作戰失敗",82,won?Cream:Color.FromArgb(220,160,145),320,250,1730,140,true);
        TextAt(g,new string('★',(int)Data.Number(battle["stars"])),72,Cream,320,415,1730,110,true);
        TextAt(g,"殲滅 "+Data.Text(battle["kills"])+" / "+Data.Text(battle["enemy_total"])+"     用時 "+(Real(battle["tick"])*.25f).ToString("0.0")+" 秒",36,Color.White,320,560,1730,90,true);
        TextAt(g,won?"演習點數 +"+Data.Text(battle["reward"]):"本次沒有獎勵",38,Cream,320,670,1730,90,true);
        Button(g,BattleStatus=="claimed"?"返回關卡":"確認結算",900,925,540,95,async()=>{if(BattleStatus=="claimed")Navigate("Stages");else await SettleBattle();},true);
    }
    void CaptureGame(string name){using(var image=new Bitmap(gameView.Width,gameView.Height)){gameView.DrawToBitmap(image,new Rectangle(0,0,image.Width,image.Height));image.Save(Path.Combine(folder,name),ImageFormat.Png);}}
    async Task WaitForGameplaySmoke(Func<bool> condition,string step){
        var deadline=DateTime.UtcNow.AddSeconds(8);
        while(!condition()&&DateTime.UtcNow<deadline)await Task.Delay(25);
        if(!condition())throw new InvalidDataException("UI action did not finish: "+step+(notice.Length==0?"":" ("+notice+")"));
    }
    void ClickGameplaySmoke(float x,float y){RenderForInput();ClickGame(new PointF(x,y));}
    async Task RunGameplaySmoke(){
        string output=Path.Combine(folder,"gameplay-smoke-result.json");
        try{
            await Connect();if(gameState==null)throw new InvalidDataException("Missing game state");
            if(HasPendingBattle)await GameCommand("abandon",Data.Obj("battle_id",battle["id"]));
            long before=Data.Number(Progress["points"]);chosenStage=10001;
            Navigate("Home");CaptureGame("preview-home.png");
            ClickGameplaySmoke(2000,710);RequireScreen("Story");
            var story=CurrentStoryScene();if(story==null||Data.Items(story["lines"]).Count<2)throw new InvalidDataException("First story scene has no readable dialogue");
            CaptureGame("preview-story.png");ClickGameplaySmoke(2000,910);
            if(storyLineIndex!=1)throw new InvalidDataException("Story next-line control did not advance");
            ClickGameplaySmoke(1000,350);
            if(storyChapterIndex!=3||Data.Items(CurrentStoryScene()["lines"]).Count==0)throw new InvalidDataException("Other story scripts were not available");
            CaptureGame("preview-story-other.png");
            ClickGameplaySmoke(200,40);RequireScreen("Home");
            ClickGameplaySmoke(1980,1000);RequireScreen("Stages");CaptureGame("preview-stages.png");
            ClickGameplaySmoke(1980,980);await WaitForGameplaySmoke(()=>screen=="Battle"&&battle!=null,"start 0-1");
            ClickGameplaySmoke(350,980);if(deployChoice.Length==0)throw new InvalidDataException("Roster card was not selected");
            ClickGameplaySmoke(800,210);await WaitForGameplaySmoke(()=>battle!=null&&Data.Items(battle["roster"]).Count(c=>Convert.ToBoolean(Data.Map(c)["deployed"]))>=1,"deploy selected card");
            ClickGameplaySmoke(1900,685);await WaitForGameplaySmoke(()=>battle!=null&&Data.Items(battle["roster"]).Count(c=>Convert.ToBoolean(Data.Map(c)["deployed"]))>=4,"quick deploy remaining cards");
            string identity=Data.Text(battle["id"]);await Task.Delay(2000);await GameCommand("state",Data.Obj());CaptureGame("preview-battle.png");
            var deadline=DateTime.UtcNow.AddSeconds(40);
            while(BattleStatus=="active"&&DateTime.UtcNow<deadline){await Task.Delay(400);await GameCommand("state",Data.Obj());}
            if(BattleStatus!="victory")throw new InvalidDataException("Expected authoritative victory, got "+BattleStatus);
            Navigate("Result");CaptureGame("preview-result.png");long reward=Data.Number(battle["reward"]);
            ClickGameplaySmoke(1100,970);await WaitForGameplaySmoke(()=>screen=="Stages"&&BattleStatus=="claimed","claim victory");
            await GameCommand("claim",Data.Obj("battle_id",identity));
            if(Data.Number(Progress["points"])!=before+reward)throw new InvalidDataException("Reward was duplicated or missing");
            await Connect();if(Data.Number(Progress["points"])!=before+reward||Data.Text(battle["id"])!=identity||BattleStatus!="claimed")throw new InvalidDataException("Settlement lost after reconnect");
            if(!Data.Map(Progress["clears"]).ContainsKey("10001"))throw new InvalidDataException("First stage clear was not saved");
            Navigate("Stages");CaptureGame("preview-stages-cleared.png");
            File.WriteAllText(output,Data.Json.Serialize(Data.Obj("success",true,"battle_id",identity,"victory",true,"first_stage_cleared",true,"ui_path_verified",true,"story_replay_verified",true,"reward_once",true,"reconnect_verified",true,"points",Progress["points"],"original_combat",false)));
        }catch(Exception ex){File.WriteAllText(output,Data.Json.Serialize(Data.Obj("success",false,"error",ex.ToString())));}
        finally{Close();}
    }
}
}
