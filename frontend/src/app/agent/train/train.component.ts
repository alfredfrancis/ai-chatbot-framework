import { Component, OnInit, Input } from '@angular/core';
import { FormGroup, FormBuilder } from '@angular/forms';
import { ActivatedRoute, Params, Router } from '@angular/router';

import { CoreService } from '../../services/core.service';
import {IntentService  } from '../../services/intent.service';

import { TrainingService } from '../../services/training.service';

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

  trainingData = [];
  newExampleText: String;
  newEntityName: String;

  message;

  trainForm: FormGroup;
  trainFormFields: any;

  testForm: FormGroup;
  testFormFields: any;

  story: any;
  
  labelled;

  constructor(
    public fb: FormBuilder,
    public storyService: IntentService,
    private _activatedRoute: ActivatedRoute,
     private _router: Router,
     private trainingService: TrainingService) {

      this.newEntityName = null;

    this.trainFormFields = {
      input: [''],
    };
    this.trainForm = this.fb.group(this.trainFormFields);

    this.testFormFields = {
      input: [''],
    };
    this.testForm = this.fb.group(this.testFormFields);

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
    
    console.log(this.story);
    if (this.story) {
      if (this.story._id && this.story._id.$oid) {
        this.story._id = this.story._id.$oid;
      }
    }
  }

  addNewExample(){
    this.trainingData.unshift({
      "text":this.newExampleText,
      "entities":[]
    })
    this.newExampleText = "";
  }


  deleteSetence(i) {
    const array = this.story.labeledSentences;
    array.splice(i, 1);
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
    let currentSelection = this.selectionInfo;
    currentSelection["name"]=this.newEntityName;
    this.newEntityName = null;
    this.trainingData[example_index]["entities"].push(currentSelection)
     console.log(this.trainingData)
  }

  annotate(){
    // snap selection to the word
    this.snapSelectionToWord();
    let result = this.getSelectionInfo() 
    if (result)
      this.selectionInfo = result;

    console.log(this.selectionInfo);  

    // let activeEl = document.getElementById("textarea_highlight");
    //   let selected = this.getSelectedText();
    //   if (selected.toString().length > 1) {
    //     let range = selected.getRangeAt(0).cloneRange();
    //     range.collapse(true);
    //     range.setStart(activeEl, 0);
    //     console.log(range);
    //   }
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
    if (window.getSelection && (sel = window.getSelection()).modify) {
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
    } else if ( (sel = document.selection) && sel.type != "Control") {
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

}
