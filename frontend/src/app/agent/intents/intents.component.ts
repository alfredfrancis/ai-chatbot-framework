import { Component, OnInit, Inject, Input } from '@angular/core';

import { ActivatedRoute, Params, Router } from '@angular/router';

import { IntentService } from '../../services/intent.service';


@Component({
  selector: 'app-intents',
  templateUrl: './intents.component.html',
  styleUrls: ['./intents.component.scss']
})
export class IntentsComponent implements OnInit {



  stories: any;

  constructor(public storyService: IntentService, private _activatedRoute: ActivatedRoute, private _router: Router) { }

  ngOnInit() {

    this.storyService.getStories().then((s: any) => {
      this.stories = s;
    });
  }


  add() {
    this._router.navigate(["/agent/default/create-intent"])
  }

  edit(story) {
    this._router.navigate(["/agent/default/edit-intent", story._id.$oid])
  }

  train(story) {

    this._router.navigate(["/agent/default/train-intent", story._id.$oid])
  }

  delete(story) {
    if (confirm('Are u sure want to delete this story?')) {
      this.storyService.deleteStory(story._id.$oid).then((s: any) => {
        this.ngOnInit();
      });
    }
  }

  build(story) {
    this.storyService.buildStory(story._id.$oid).then((s: any) => {
      this.ngOnInit();
    });
  }
}
