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

  addTest() {

  }

  buildModel() {
    this.storyService.buildStory(this.story._id)
      .then(c => {
        this.message = 'Build sucessfull';
      })
      .catch(c => {
        this.message = 'Error on Building';
      })
  }

  clear() {
    this.trainForm.reset();
  }

  startLabeling() {
    const form = this.trainForm.value;
    this.trainingService.startLabeling(form.input)
      .then(c => {
        this.labelled = c;
        // this.message = 'Build sucessfull';
      })
      .catch(c => {
        this.message = 'Error on labelling';
      })
  }

  deleteSetence(i) {
    const array = this.story.labeledSentences;
    array.splice(i, 1);
  }
  
  getSelectionInfo(){
    let selection = window.getSelection(); 
    return {
      "value":selection.toString(),
      "begin":selection.anchorOffset,
      "end": selection.extentOffset
    }
  }

  addNewEntity(example_index){
    let currentSelection = this.selectionInfo;
    currentSelection["name"]=this.newEntityName;
    this.newEntityName = null;
    this.trainingData[example_index]["entities"].push(currentSelection)
     console.log(this.trainingData)
  }

  annotate(){
    this.selectionInfo = this.getSelectionInfo();

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


}
