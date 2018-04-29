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

  intent: any;
  intentForm: FormGroup;
  intentFormFields: any;

  intentTypes;
  intentTypesArray;
  message;

  constructor(
    public fb: FormBuilder,
    public coreService: CoreService,
    public intentService: IntentService,
    private _activatedRoute: ActivatedRoute, private _router: Router) {


      this.intentTypes = IntentService.intentTypes;
      this.intentTypesArray = Object.keys(this.intentTypes);

      
  }

  loadForm(){
    this.intentFormFields = {
      _id: [''],
      name: [''],
      intentId: [''],
      userDefined: [true],
      speechResponse: [''],
      apiTrigger: [''],
      apiDetails: this.initApiDetails(),
      parameters: this.fb.array(
        this.intent && this.intent.parameters ? this.intent.parameters.map(n => {
          return this.initParameter(n);
        }) : []
      )
    };
    this.intentForm = this.fb.group(this.intentFormFields);
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
        this.intent = data.story;
        this.loadForm();
        this.coreService.setDataForm(this.intentForm, this.intentFormFields, this.intent);
    });   



  }

  addParameter() {
    const control = <FormArray>this.intentForm.controls['parameters'];
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
    const control = <FormArray>this.intentForm.controls['parameters'];
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
    const form = this.intentForm.value;
    if (form._id && form._id.$oid) {
      form._id = form._id.$oid;
    }
    if (!this.apiTrigger()) {
      delete form.apiDetails;
    }

    this.intentService.saveIntent(form)
      .then(c => {
        this.message = 'Intent created!';
        this._router.navigate(["/agent/default/edit-intent", c["_id"]])
      })
  }

  apiTrigger() {
    return this.intentForm.value.apiTrigger;
  }

}
