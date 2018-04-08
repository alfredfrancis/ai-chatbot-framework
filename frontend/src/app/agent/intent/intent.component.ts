import { Component, OnInit, Input } from '@angular/core';
import { FormGroup, FormBuilder, FormArray } from '@angular/forms';
import { ActivatedRoute, Params, Router } from '@angular/router';

import { CoreService } from '../../services/core.service';
import {IntentService  } from '../../services/intent.service';

@Component({
  selector: 'app-intent',
  templateUrl: './intent.component.html',
  styleUrls: ['./intent.component.scss']
})
export class IntentComponent implements OnInit {

  story: any;
  storyForm: FormGroup;
  storyFormFields: any;

  storyTypes;
  storyTypesArray;
  message;

  constructor(
    public fb: FormBuilder,
    public coreService: CoreService,
    public storyService: IntentService,
    private _activatedRoute: ActivatedRoute, private _router: Router) {


      this.storyTypes = IntentService.storyTypes;
      this.storyTypesArray = Object.keys(this.storyTypes);

      
  }

  loadForm(){
    this.storyFormFields = {
      _id: [''],
      storyName: [''],
      intentName: [''],
      speechResponse: [''],
      apiTrigger: [''],
      apiDetails: this.initApiDetails(),
      parameters: this.fb.array(
        this.story && this.story.parameters ? this.story.parameters.map(n => {
          return this.initParameter(n);
        }) : []
      )
    };
    this.storyForm = this.fb.group(this.storyFormFields);
  }

  ngOnInit() {
    this.loadForm()

    this._activatedRoute.params.subscribe((params: Params) => {
      console.log("active agent reached " + params['intent_id'])
    });


    this._activatedRoute.data
      .subscribe((data:{story:any}) => {
        console.log("selected intent =>>")
        console.log(data.story)
        this.story = data.story;
        this.loadForm();
        this.coreService.setDataForm(this.storyForm, this.storyFormFields, this.story);
    });   



  }

  addParameter() {
    const control = <FormArray>this.storyForm.controls['parameters'];
    control.push(this.initParameter());
  }

  initParameter(parameter = null) {
    const fields = {
      name: [''],
      type: [''],
      required: [false],
      prompt: ['']
    };
    const g = this.fb.group(fields);
    if (parameter) {
      // setdataform
    }
    return g;
  }

  deleteParameter(i) {
    const control = <FormArray>this.storyForm.controls['parameters'];
    control.removeAt(i);
  }


  initApiDetails(parameter = null) {
    const fields = {
      isJson: [''],
      url: [''],
      requestType: [''],
      jsonData: ['']
    };
    const g = this.fb.group(fields);
    if (parameter) {
      // setdataform
    }
    return g;
  }

  save() {
    const form = this.storyForm.value;
    if (form._id && form._id.$oid) {
      form._id = form._id.$oid;
    }
    if (!this.apiTrigger()) {
      delete form.apiDetails;
    }

    this.storyService.saveStory(form)
      .then(c => {
        this.message = 'Story created!';
        this._router.navigate(["/agent/default/edit-intent", c["_id"]])
      })
  }

  apiTrigger() {
    return this.storyForm.value.apiTrigger;
  }

}
