import { Component, OnInit } from '@angular/core';
import { StoryService } from './story.service';

@Component({
  selector: 'app-train',
  templateUrl: './train.component.html',
  // styleUrls: ['./train.component.css']
})
export class TrainComponent implements OnInit {

  constructor(public storyService: StoryService) { }

  ngOnInit() {
  }

}
