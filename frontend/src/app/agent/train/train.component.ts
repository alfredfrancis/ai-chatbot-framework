

import { Component, OnInit, Input } from '@angular/core';
import { FormGroup, FormBuilder } from '@angular/forms';
import { ActivatedRoute, Params, Router } from '@angular/router';

import { CoreService } from '../../services/core.service';
import {IntentService  } from '../../services/intent.service';



@Component({
  selector: 'app-train',
  templateUrl: './train.component.html',
  styleUrls: ['./train.component.scss']
})
export class TrainComponent implements OnInit {

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
    private _activatedRoute: ActivatedRoute, private _router: Router) {

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
      console.log("active agent reached " + params['intent_id'])
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
    this.storyService.startLabeling(form.input)
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



}
