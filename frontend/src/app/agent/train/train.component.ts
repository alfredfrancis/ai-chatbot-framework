import { Component, OnInit, Input } from '@angular/core';
import { FormGroup, FormBuilder } from '@angular/forms';
import { ActivatedRoute, Params, Router } from '@angular/router';

import {IntentService  } from '../../services/intent.service';

import { TrainingService } from '../../services/training.service';
import { EntitiesService } from '../../services/entities.service'

@Component({
  selector: 'app-train',
  templateUrl: './train.component.html',
  styleUrls: ['./train.component.scss']
})
export class TrainComponent implements OnInit {

  selectionInfo = {
    "value":"",
    "begin":0,
    "end":0
  };

  intentId:string = null ;
  trainingData: Array<any>;
  newExampleText: String;
  newEntityName: String;

  story: any;
  entities: Array<any> = [];

  constructor(
    public storyService: IntentService,
    private _activatedRoute: ActivatedRoute,
     private _router: Router,
     private trainingService: TrainingService,
     private entitiesService: EntitiesService) {

      this.trainingData = []

      this.newEntityName = null;
  }

  ngOnInit() {
    this._activatedRoute.params.subscribe((params: Params) => {
      console.log("current intent " + params['intent_id'])
      this.intentId = params['intent_id']
      this.trainingService.getTrainingData(params['intent_id']).then(
        (result: Array<any>)=>{
          this.trainingData = result;
        }
      )

    });


    this._activatedRoute.data
      .subscribe((data:{story:any}) => {
        console.log("selected intent =>>")
        console.log(data.story)
        this.story = data.story;

    });  

    if (this.story) {
      if (this.story._id && this.story._id.$oid) {
        this.story._id = this.story._id.$oid;
      }
    }

    this.entitiesService.getEntities().then(
      (result: Array<any>) => {
        this.entities = result
      }
    )
    
  }

  // 123456
  getAnnotatedText(example){
    let text = example.text
    example.entities.forEach(entity => {
      var key =entity.value;
      var regex = new RegExp(key,'g');
      text =  text.replace(regex,'&nbsp;<mark style="background: red;">'+key+'</mark>&nbsp;' );
    });
    return text
  }
  // updateValue($event,example_index){
  //   this.trainingData[example_index]["text"]=$event.srcElement.outerText;
    
  // }

  addNewExample(){
    this.trainingData.unshift({
      "text":this.newExampleText,
      "entities":[]
    })
    this.newExampleText = "";
  }

  deleteExample(example_index){
    this.trainingData.splice(example_index,1)
  }

  deleteEntity(example_index,entity_index){
    this.trainingData[example_index].entities.splice(entity_index,1)

  }
  
  getSelectionInfo():any {
    let selection = window.getSelection(); 
    if (selection.anchorOffset == selection.extentOffset)
      return false;
      
    let result = {
      "value":selection.toString(),
    }

    if (selection.anchorOffset > selection.extentOffset)
    {
      result["begin"] = selection.extentOffset;
      result["end"] = selection.anchorOffset;
    }
    else if (selection.anchorOffset < selection.extentOffset){
      result["begin"] = selection.anchorOffset;
      result["end"] = selection.extentOffset;
    }

    return result;

  }

  addNewEntity(example_index){
    this.trainingData[example_index]["entities"].push({
      "value":this.selectionInfo.value,
      "begin":this.selectionInfo.begin,
      "end":this.selectionInfo.end,
      "name":this.newEntityName
    })
    this.newEntityName = null;
  }

  annotate(){
    // snap selection to the word
    this.snapSelectionToWord();
    let result = this.getSelectionInfo() 
    if (result)
      this.selectionInfo = result;

    console.log(this.selectionInfo);  
  }

  updateTrainingData(){
    this.trainingService.saveTrainingData(this.intentId,this.trainingData).then(()=>{
      console.log("Success");
    })
  }

  snapSelectionToWord() {
    var sel;

    // Check for existence of window.getSelection() and that it has a
    // modify() method. IE 9 has both selection APIs but no modify() method.
    if (window.getSelection && (<any>(sel = window.getSelection())).modify) {
        sel = window.getSelection();
        if (!sel.isCollapsed) {

            // Detect if selection is backwards
            var range = document.createRange();
            range.setStart(sel.anchorNode, sel.anchorOffset);
            range.setEnd(sel.focusNode, sel.focusOffset);
            var backwards = range.collapsed;
            range.detach();

            // modify() works on the focus of the selection
            var endNode = sel.focusNode, endOffset = sel.focusOffset;
            sel.collapse(sel.anchorNode, sel.anchorOffset);

            var direction = [];
            if (backwards) {
                direction = ['backward', 'forward'];
            } else {
                direction = ['forward', 'backward'];
            }

            sel.modify("move", direction[0], "character");
            sel.modify("move", direction[1], "word");
            sel.extend(endNode, endOffset);
            sel.modify("extend", direction[1], "character");
            sel.modify("extend", direction[0], "word");
        }
    } else if ( (sel = (<any>document).selection) && sel.type != "Control") {
        var textRange = sel.createRange();
        if (textRange.text) {
            textRange.expand("word");
            // Move the end back to not include the word's trailing space(s),
            // if necessary
            while (/\s$/.test(textRange.text)) {
                textRange.moveEnd("character", -1);
            }
            textRange.select();
        }
    }
}

//place curser at the end of content editable div
  placeCaretAtEnd(el) {
    el.focus();
    if (typeof window.getSelection != "undefined"
            && typeof document.createRange != "undefined") {
        var range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
    } else if (typeof (<any>document.body).createTextRange != "undefined") {
        var textRange = (<any>document.body).createTextRange();
        textRange.moveToElementText(el);
        textRange.collapse(false);
        textRange.select();
    }
  }

}
