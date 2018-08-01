import { Component, OnInit } from '@angular/core';
import { EntitiesService } from '../../services/entities.service'
import {Router} from "@angular/router";
import {UtilsService} from "../../services/utils.service";
@Component({
  selector: 'app-entities',
  templateUrl: './entities.component.html',
  styleUrls: ['./entities.component.scss']
})
export class EntitiesComponent implements OnInit {

  constructor(private _router: Router, private coreService:UtilsService, private entitiesService: EntitiesService) { }

  entities = []

  ngOnInit() {
    this.entitiesService.getEntities().then(
      (result: Array<any>) => {
        this.entities = result
      }
    )
  }

  newEntity(name) {
    if (this.entities.find(x => x.name === name)) {
      alert("Entity already exist");
      return;
    }
    this.entitiesService.create_entity({ "name": name }).then(
      (result) => {
        this.entities.push({
          "_id":{
            "$oid":result["_id"]
          },
          "name": name
        })
      }
    )
  }

  edit(entity) {
    this._router.navigate(["/agent/default/edit-entity", entity._id.$oid])
  }

  deleteEntity(id,i){
    if (confirm('Are u sure want to delete this entity?')) {
      this.coreService.displayLoader(true);
      this.entitiesService.delete_entity(id).then(
        () => {
          this.entities.splice(i, 1);
          this.ngOnInit();
          this.coreService.displayLoader(false);
      });
    }
  }

}
