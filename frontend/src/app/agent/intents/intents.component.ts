import { Component, OnInit, Inject, Input } from '@angular/core';

import { ActivatedRoute, Params, Router } from '@angular/router';

import { IntentService } from '../../services/intent.service';
import {TrainingService} from '../../services/training.service'

@Component({
  selector: 'app-intents',
  templateUrl: './intents.component.html',
  styleUrls: ['./intents.component.scss']
})
export class IntentsComponent implements OnInit {



  intents: any;

  constructor(public intentService: IntentService, private _activatedRoute: ActivatedRoute,
     private _router: Router,private trainingService:TrainingService) { }

  ngOnInit() {

    this.intentService.getIntents().then((s: any) => {
      this.intents = s;
    });
  }


  add() {
    this._router.navigate(["/agent/default/create-intent"])
  }

  edit(intent) {
    this._router.navigate(["/agent/default/edit-intent", intent._id.$oid])
  }

  train(intent) {
    this._router.navigate(["/agent/default/train-intent", intent._id.$oid])
  }

  delete(intent) {
    if (confirm('Are u sure want to delete this story?')) {
      this.intentService.delete_intent(intent._id.$oid).then((s: any) => {
        this.ngOnInit();
      });
    }
  }

  trainModels() {
    this.trainingService.trainModels().then((s: any) => {
      this.ngOnInit();
    });
  }
}
