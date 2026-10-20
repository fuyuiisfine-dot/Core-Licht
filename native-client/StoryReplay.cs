using System;
using System.IO;
using System.Linq;
using System.Drawing;
using System.Collections.Generic;

namespace CoreLicht {
public partial class ClientWindow {
    readonly List<Dictionary<string,object>> storyChapters=new List<Dictionary<string,object>>();
    readonly HashSet<string> storySeen=new HashSet<string>();
    string storyLoadError="";
    int storyChapterIndex,storySceneIndex,storyLineIndex,storyListOffset;

    void SetupStoryReplay(){
        string path=Path.Combine(folder,"story.json");
        if(!File.Exists(path)){storyLoadError="尚未準備劇情資料。";return;}
        try{
            var data=Data.Read(path);
            if(Data.Text(data["format"])!="corelicht-story-replay-v1")throw new InvalidDataException("Unknown story format");
            storyChapters.AddRange(Data.Items(data["chapters"]).Select(Data.Map));
        }catch(Exception ex){storyChapters.Clear();storyLoadError="劇情資料無法載入："+ex.Message;}
    }
    void SetStoryHistory(Dictionary<string,object> history){
        storySeen.Clear();
        foreach(var item in Data.Items(history["list"]))storySeen.Add(Data.Text(Data.Map(item)["k"]));
        if(gameView!=null)gameView.Invalidate();
    }
    List<Dictionary<string,object>> StoryScenes(){
        if(storyChapters.Count==0)return new List<Dictionary<string,object>>();
        storyChapterIndex=Math.Max(0,Math.Min(storyChapterIndex,storyChapters.Count-1));
        return Data.Items(storyChapters[storyChapterIndex]["scenes"]).Select(Data.Map).ToList();
    }
    Dictionary<string,object> CurrentStoryScene(){
        var scenes=StoryScenes();if(scenes.Count==0)return null;
        storySceneIndex=Math.Max(0,Math.Min(storySceneIndex,scenes.Count-1));
        return scenes[storySceneIndex];
    }
    void SelectStoryChapter(int index){storyChapterIndex=index;storySceneIndex=0;storyLineIndex=0;storyListOffset=0;gameView.Invalidate();}
    void SelectStoryScene(int index){storySceneIndex=index;storyLineIndex=0;gameView.Invalidate();}
    void ScrollStory(int direction){storyListOffset=Math.Max(0,Math.Min(Math.Max(0,StoryScenes().Count-8),storyListOffset+direction));}

    void DrawStoryReplay(Graphics g){
        TextAt(g,"劇情回顧",59,Cream,170,128,950,98);
        if(storyChapters.Count==0){TextAt(g,storyLoadError,35,Color.White,170,300,1700,110);return;}
        TextAt(g,"從本機遊戲備份整理的原版繁中對話",27,Color.White,170,220,1000,65);
        for(int i=0;i<storyChapters.Count;i++){
            int index=i;float x=170+i*245;var chapter=storyChapters[i];bool selectedChapter=i==storyChapterIndex;
            Rect(g,selectedChapter?Color.FromArgb(205,132,117,76):Color.FromArgb(190,28,31,31),x,306,232,84);
            TextAt(g,Data.Text(chapter["title"])+"  "+Data.Text(chapter["name"]),25,selectedChapter?Color.White:Cream,x+8,306,216,84,true);
            Hit(x,306,232,84,()=>SelectStoryChapter(index));
        }
        var scenes=StoryScenes();storyListOffset=Math.Min(storyListOffset,Math.Max(0,scenes.Count-8));
        Rect(g,Color.FromArgb(180,20,23,23),170,410,975,555);
        for(int i=storyListOffset;i<Math.Min(scenes.Count,storyListOffset+8);i++){
            int index=i;float y=424+(i-storyListOffset)*66;var scene=scenes[i];bool active=i==storySceneIndex;
            Rect(g,active?Color.FromArgb(190,135,119,78):Color.FromArgb(80,70,75,72),184,y,945,57);
            TextAt(g,Data.Text(scene["name"]),29,active?Color.White:Cream,200,y,660,57);
            string state=Data.Items(scene["lines"]).Count==0?"無對話":storySeen.Contains(Data.Text(scene["id"]))?"已讀":"未讀";
            TextAt(g,state,24,active?Color.White:Color.LightGray,957,y,150,57,true);
            Hit(184,y,945,57,()=>SelectStoryScene(index));
        }
        Button(g,"上一頁",170,979,195,66,()=>{storyListOffset=Math.Max(0,storyListOffset-8);});
        TextAt(g,(storyListOffset+1)+" - "+Math.Min(scenes.Count,storyListOffset+8)+" / "+scenes.Count,26,Cream,460,979,360,66,true);
        Button(g,"下一頁",950,979,195,66,()=>{storyListOffset=Math.Min(Math.Max(0,scenes.Count-8),storyListOffset+8);});

        var current=CurrentStoryScene();if(current==null)return;
        Rect(g,Color.FromArgb(205,20,23,23),1180,130,995,835);
        TextAt(g,Data.Text(current["name"]),48,Cream,1220,155,915,85);
        TextAt(g,Data.Text(current["subtitle"]),30,Color.White,1220,245,915,55);
        TextAt(g,Data.Text(current["summary"]),27,Color.FromArgb(210,Cream),1220,310,915,86);
        Line(g,Cream,1215,411,2140,411,2);
        var lines=Data.Items(current["lines"]).Select(Data.Map).ToList();
        if(lines.Count==0){TextAt(g,"這一段尚無可回顧的對話。",34,Color.White,1220,465,900,230,true);return;}
        storyLineIndex=Math.Max(0,Math.Min(storyLineIndex,lines.Count-1));
        var line=lines[storyLineIndex];string speaker=Data.Text(line["speaker"]);
        if(speaker=="居中顯示")speaker="旁白";
        TextAt(g,speaker,37,Cream,1230,452,860,65);
        TextAt(g,Data.Text(line["text"]),38,Color.White,1230,530,890,268);
        TextAt(g,(storyLineIndex+1)+" / "+lines.Count,27,Cream,1510,820,330,55,true);
        Button(g,"上一句",1210,875,280,65,()=>{storyLineIndex=Math.Max(0,storyLineIndex-1);});
        Button(g,"下一句",1860,875,280,65,()=>{storyLineIndex=Math.Min(lines.Count-1,storyLineIndex+1);},true);
    }
}
}
